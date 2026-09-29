"""教师端蓝图 - 学生管理、学习进度监控、画像分析"""
import json, logging
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func as sa_func

from models import (
    db, User, Assessment, EvaluationReport, LearningBehavior,
    TutorSession, LearningPath, WrongQuestion, KnowledgePoint,
    LearningPlan, ProfileConversation
)
from config import LEVELS, SUBJECTS
from evaluation_engine import BehaviorTracker

logger = logging.getLogger(__name__)

teacher_bp = Blueprint('teacher_bp', __name__)


# ============================================================
# 辅助函数
# ============================================================

def _get_student_profile_info(user_id):
    """获取学生等级和学科信息。
    优先从 ProfileConversation（对话画像）获取，fallback 到 Assessment（测评）。
    返回: {'level_id': int, 'level_name': str, 'subject': str, 'source': str}
    """
    level_names = {1: '基础', 2: '中等', 3: '高等', 4: '大神'}

    # 1) 优先查对话画像
    cp = ProfileConversation.query.filter_by(
        user_id=user_id, is_complete=True
    ).order_by(ProfileConversation.updated_at.desc()).first()
    if cp and cp.profile_data:
        try:
            profile = json.loads(cp.profile_data) if isinstance(cp.profile_data, str) else cp.profile_data
            level_id = int(profile.get('level', 0)) or 1
            if 1 <= level_id <= 4:
                return {
                    'level_id': level_id,
                    'level_name': profile.get('level_name') or level_names.get(level_id, '基础'),
                    'subject': profile.get('major', '') or 'computer_science',
                    'source': 'profile'
                }
        except Exception:
            pass

    # 2) fallback 到测评
    latest_asmt = Assessment.query.filter_by(user_id=user_id)\
        .order_by(Assessment.created_at.desc()).first()
    if latest_asmt:
        return {
            'level_id': latest_asmt.level_id or 1,
            'level_name': latest_asmt.level_name or level_names.get(latest_asmt.level_id, '基础'),
            'subject': latest_asmt.subject or 'computer_science',
            'source': 'assessment'
        }

    # 3) 默认值
    return {'level_id': 1, 'level_name': '基础', 'subject': 'computer_science', 'source': 'default'}


def _get_all_students_level_distribution():
    """统计所有学生的等级分布（基于画像+测评）"""
    students = User.query.filter(User.is_admin == False).all()
    level_dist = {}
    subject_dist = {}
    for s in students:
        info = _get_student_profile_info(s.id)
        lvl = info['level_id']
        level_dist[lvl] = level_dist.get(lvl, 0) + 1
        subj = info['subject']
        if subj:
            subject_dist[subj] = subject_dist.get(subj, 0) + 1
    return level_dist, subject_dist


# ============================================================
# 页面路由
# ============================================================

def _check_teacher_access():
    """检查当前用户是否有教师端访问权限（管理员或教师）"""
    if not (getattr(current_user, 'is_admin', False) or getattr(current_user, 'is_teacher', False)):
        from flask import abort
        abort(403)

@teacher_bp.route('/teacher')
@login_required
def teacher_dashboard():
    """教师端主页 - 学生总览"""
    _check_teacher_access()

    # 统计信息
    total_students = User.query.filter(User.is_admin == False).count()

    # 按等级分布（基于画像+测评）
    level_dist, _ = _get_all_students_level_distribution()
    level_names_map = {1: '基础', 2: '中等', 3: '高等', 4: '大神'}
    level_distribution = {f"等级{l}·{level_names_map.get(l, '')}": c for l, c in level_dist.items() if l}

    # 今日活跃学生
    today = datetime.now().date()
    active_today = LearningBehavior.query.filter(
        sa_func.date(LearningBehavior.created_at) == today
    ).distinct(LearningBehavior.user_id).count()

    # 最近7天学习行为趋势
    week_ago = datetime.now() - timedelta(days=7)
    weekly_behaviors = LearningBehavior.query.filter(
        LearningBehavior.created_at >= week_ago
    ).all()

    daily_activity = defaultdict(int)
    for b in weekly_behaviors:
        day = b.created_at.strftime('%m-%d')
        daily_activity[day] += 1

    # 本周升级人数（本周内完成画像或测评的学生）
    week_levelup = ProfileConversation.query.filter(
        ProfileConversation.is_complete == True,
        ProfileConversation.updated_at >= week_ago
    ).distinct(ProfileConversation.user_id).count()

    levels_dict = {lv['id']: lv['name'] for lv in LEVELS}

    return render_template('teacher/dashboard.html',
        total_students=total_students,
        active_today=active_today,
        level_distribution=json.dumps(level_distribution),
        daily_activity=json.dumps(dict(sorted(daily_activity.items()))),
        subjects=SUBJECTS,
        levels=levels_dict,
        week_levelup=week_levelup
    )


@teacher_bp.route('/teacher/students')
@login_required
def teacher_students():
    """学生列表 - 按画像等级分区"""
    _check_teacher_access()
    # 获取筛选参数
    level_filter = request.args.get('level', type=int)
    subject_filter = request.args.get('subject', '')
    search_query = request.args.get('q', '').strip()
    
    # 基础查询：非管理员用户都是学生
    query = User.query.filter(User.is_admin == False)
    
    if search_query:
        query = query.filter(
            db.or_(
                User.username.contains(search_query),
                User.bio.contains(search_query)
            )
        )
    
    students = query.order_by(User.created_at.desc()).all()
    
    # 为每个学生补充画像数据
    student_list = []
    for s in students:
        # 获取等级和学科（优先画像，fallback测评）
        info = _get_student_profile_info(s.id)

        # 最新评估报告
        latest_eval = EvaluationReport.query.filter_by(user_id=s.id)\
            .order_by(EvaluationReport.created_at.desc()).first()

        # 学习积分
        learning_score = BehaviorTracker.calculate_learning_score(s.id)

        # 最近活跃时间
        last_active = LearningBehavior.query.filter_by(user_id=s.id)\
            .order_by(LearningBehavior.created_at.desc()).first()

        # 错题数量
        wrong_count = WrongQuestion.query.filter_by(
            user_id=s.id, is_mastered=False
        ).count()

        # 知识点数量
        kp_count = KnowledgePoint.query.filter_by(user_id=s.id).count()

        profile = {
            'id': s.id,
            'username': s.username,
            'avatar': s.avatar or '👤',
            'bio': s.bio or '',
            'created_at': s.created_at.strftime('%Y-%m-%d') if s.created_at else '',
            'level_id': info['level_id'],
            'level_name': info['level_name'],
            'overall_score': latest_eval.overall_score if latest_eval else None,
            'learning_score': learning_score,
            'last_active': last_active.created_at.strftime('%m-%d %H:%M') if last_active else '从未',
            'wrong_count': wrong_count,
            'kp_count': kp_count,
            'subject': info['subject']
        }

        # 应用筛选
        if level_filter and profile['level_id'] != level_filter:
            continue
        if subject_filter and profile['subject'] != subject_filter:
            continue

        student_list.append(profile)
    
    # 按等级分组
    level_groups = defaultdict(list)
    for s in student_list:
        level_groups[s['level_id']].append(s)
    
    levels_dict = {lv['id']: lv['name'] for lv in LEVELS}

    total_wrong = sum(s['wrong_count'] for s in student_list)

    return render_template('teacher/students.html',
        students=student_list,
        level_groups=dict(sorted(level_groups.items())),
        levels=levels_dict,
        subjects=SUBJECTS,
        current_level=level_filter,
        current_subject=subject_filter,
        search_query=search_query,
        total_wrong=total_wrong
    )


@teacher_bp.route('/teacher/student/<int:student_id>')
@login_required
def teacher_student_detail(student_id):
    """学生详情页 - 学习进度、错题、知识点"""
    _check_teacher_access()
    student = User.query.get_or_404(student_id)
    
    # 学习历程时间线
    behaviors = LearningBehavior.query.filter_by(user_id=student_id)\
        .order_by(LearningBehavior.created_at.desc()).limit(50).all()
    
    behavior_timeline = []
    for b in behaviors:
        behavior_timeline.append({
            'type': b.behavior_type,
            'resource_type': b.resource_type,
            'time_spent': b.time_spent,
            'score': b.score,
            'created_at': b.created_at.strftime('%m-%d %H:%M'),
            'detail': json.loads(b.detail) if b.detail else {}
        })
    
    # 测评历史
    assessments = Assessment.query.filter_by(user_id=student_id)\
        .order_by(Assessment.created_at.desc()).all()
    
    assessment_history = []
    for a in assessments:
        assessment_history.append({
            'subject': a.subject,
            'total_score': a.total_score,
            'level_name': a.level_name,
            'created_at': a.created_at.strftime('%Y-%m-%d')
        })
    
    # 评估报告
    eval_reports = EvaluationReport.query.filter_by(user_id=student_id)\
        .order_by(EvaluationReport.created_at.desc()).all()
    
    # 错题分析
    wrong_questions = WrongQuestion.query.filter_by(
        user_id=student_id, is_mastered=False
    ).order_by(WrongQuestion.created_at.desc()).all()
    
    # 按知识点聚类错题
    weakness_clusters = defaultdict(list)
    for wq in wrong_questions:
        kp = wq.knowledge_point or '未分类'
        weakness_clusters[kp].append({
            'question': wq.question[:100] + '...' if len(wq.question) > 100 else wq.question,
            'difficulty': wq.difficulty,
            'source': wq.source,
            'created_at': wq.created_at.strftime('%m-%d')
        })
    
    # 知识点掌握情况
    knowledge_points = KnowledgePoint.query.filter_by(user_id=student_id)\
        .order_by(KnowledgePoint.mastery_level.asc()).all()
    
    kp_list = []
    for kp in knowledge_points:
        kp_list.append({
            'name': kp.name,
            'subject': kp.subject,
            'mastery_level': round(kp.mastery_level * 100, 1),
            'study_count': kp.study_count,
            'last_study': kp.last_study_time.strftime('%m-%d') if kp.last_study_time else ''
        })
    
    # 辅导会话记录
    tutor_sessions = TutorSession.query.filter_by(user_id=student_id)\
        .order_by(TutorSession.created_at.desc()).limit(20).all()
    
    tutor_history = []
    for ts in tutor_sessions:
        tutor_history.append({
            'subject': ts.subject,
            'question': ts.question[:80] + '...' if ts.question and len(ts.question) > 80 else (ts.question or ''),
            'created_at': ts.created_at.strftime('%m-%d %H:%M')
        })
    
    # 学习路径
    learning_paths = LearningPath.query.filter_by(user_id=student_id)\
        .order_by(LearningPath.created_at.desc()).all()
    
    return render_template('teacher/student_detail.html',
        student=student,
        behavior_timeline=behavior_timeline,
        assessment_history=assessment_history,
        eval_reports=eval_reports,
        weakness_clusters=dict(weakness_clusters),
        knowledge_points=kp_list,
        tutor_history=tutor_history,
        learning_paths=learning_paths,
        subjects=SUBJECTS
    )


@teacher_bp.route('/teacher/analytics')
@login_required
def teacher_analytics():
    """数据分析页 - 班级整体学习情况"""
    _check_teacher_access()
    # 学科和等级分布（基于画像+测评）
    level_dist, subject_dist_raw = _get_all_students_level_distribution()
    level_names_map = {1: '基础', 2: '中等', 3: '高等', 4: '大神'}
    subject_names_map = SUBJECTS
    subject_dist = {subject_names_map.get(s, s): c for s, c in subject_dist_raw.items() if s}
    level_distribution = {f"等级{l}·{level_names_map.get(l, '')}": c for l, c in level_dist.items() if l}

    # 平均学习时长（最近7天）
    week_ago = datetime.now() - timedelta(days=7)
    avg_time = db.session.query(
        sa_func.avg(LearningBehavior.time_spent)
    ).filter(LearningBehavior.created_at >= week_ago).scalar()

    # 高频错题知识点
    hot_weaknesses = db.session.query(
        WrongQuestion.knowledge_point,
        sa_func.count(WrongQuestion.id)
    ).filter(
        WrongQuestion.is_mastered == False,
        WrongQuestion.knowledge_point.isnot(None)
    ).group_by(WrongQuestion.knowledge_point)\
     .order_by(sa_func.count(WrongQuestion.id).desc())\
     .limit(10).all()

    # 学习行为类型分布
    behavior_dist = db.session.query(
        LearningBehavior.behavior_type,
        sa_func.count(LearningBehavior.id)
    ).group_by(LearningBehavior.behavior_type).all()

    return render_template('teacher/analytics.html',
        subject_dist=json.dumps(subject_dist),
        level_dist=json.dumps(level_distribution),
        avg_time=round(avg_time or 0, 1),
        hot_weaknesses=hot_weaknesses,
        behavior_dist=json.dumps({b: c for b, c in behavior_dist})
    )


# ============================================================
# API 路由
# ============================================================

@teacher_bp.route('/api/teacher/students', methods=['GET'])
@login_required
def api_teacher_students():
    """API: 获取学生列表（支持筛选和分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    level = request.args.get('level', type=int)
    subject = request.args.get('subject', '')
    
    query = User.query.filter(User.is_admin == False)
    
    # 获取所有学生再筛选（因为等级信息在关联表中）
    students = query.order_by(User.created_at.desc()).all()
    
    result = []
    for s in students:
        info = _get_student_profile_info(s.id)
        latest_eval = EvaluationReport.query.filter_by(user_id=s.id)\
            .order_by(EvaluationReport.created_at.desc()).first()

        if level and info['level_id'] != level:
            continue
        if subject and info['subject'] != subject:
            continue

        result.append({
            'id': s.id,
            'username': s.username,
            'avatar': s.avatar or '👤',
            'level_id': info['level_id'],
            'level_name': info['level_name'],
            'subject': info['subject'],
            'overall_score': latest_eval.overall_score if latest_eval else None,
            'learning_score': BehaviorTracker.calculate_learning_score(s.id),
            'created_at': s.created_at.isoformat() if s.created_at else None
        })
    
    # 手动分页
    total = len(result)
    start = (page - 1) * per_page
    end = start + per_page
    
    return jsonify({
        'students': result[start:end],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })


@teacher_bp.route('/api/teacher/student/<int:student_id>/progress', methods=['GET'])
@login_required
def api_student_progress(student_id):
    """API: 获取学生学习进度"""
    student = User.query.get_or_404(student_id)
    
    # 最近30天学习行为统计
    month_ago = datetime.now() - timedelta(days=30)
    behaviors = LearningBehavior.query.filter(
        LearningBehavior.user_id == student_id,
        LearningBehavior.created_at >= month_ago
    ).all()
    
    daily_stats = defaultdict(lambda: {'count': 0, 'time': 0})
    for b in behaviors:
        day = b.created_at.strftime('%Y-%m-%d')
        daily_stats[day]['count'] += 1
        daily_stats[day]['time'] += b.time_spent or 0
    
    # 学科分布
    subject_stats = defaultdict(lambda: {'count': 0, 'time': 0})
    for b in behaviors:
        if b.subject:
            subject_stats[b.subject]['count'] += 1
            subject_stats[b.subject]['time'] += b.time_spent or 0
    
    # 能力维度评分（从最新评估报告）
    latest_eval = EvaluationReport.query.filter_by(user_id=student_id)\
        .order_by(EvaluationReport.created_at.desc()).first()
    
    dimensions = {}
    if latest_eval and latest_eval.dimension_scores:
        try:
            dimensions = json.loads(latest_eval.dimension_scores)
        except:
            pass
    
    return jsonify({
        'student': {
            'id': student.id,
            'username': student.username,
            'avatar': student.avatar or '👤'
        },
        'daily_activity': dict(sorted(daily_stats.items())),
        'subject_distribution': dict(subject_stats),
        'dimensions': dimensions,
        'learning_score': BehaviorTracker.calculate_learning_score(student_id)
    })


@teacher_bp.route('/api/teacher/student/<int:student_id>/weaknesses', methods=['GET'])
@login_required
def api_student_weaknesses(student_id):
    """API: 获取学生错题和薄弱知识点"""
    # 错题统计
    wrong_stats = db.session.query(
        WrongQuestion.knowledge_point,
        WrongQuestion.difficulty,
        sa_func.count(WrongQuestion.id)
    ).filter(
        WrongQuestion.user_id == student_id,
        WrongQuestion.is_mastered == False
    ).group_by(WrongQuestion.knowledge_point, WrongQuestion.difficulty)\
     .order_by(sa_func.count(WrongQuestion.id).desc()).all()
    
    # 薄弱知识点（掌握度 < 0.6）
    weak_kps = KnowledgePoint.query.filter(
        KnowledgePoint.user_id == student_id,
        KnowledgePoint.mastery_level < 0.6
    ).order_by(KnowledgePoint.mastery_level.asc()).all()
    
    return jsonify({
        'wrong_question_stats': [
            {
                'knowledge_point': kp or '未分类',
                'difficulty': d,
                'count': c
            }
            for kp, d, c in wrong_stats
        ],
        'weak_knowledge_points': [
            {
                'name': kp.name,
                'subject': kp.subject,
                'mastery_level': round(kp.mastery_level * 100, 1),
                'study_count': kp.study_count
            }
            for kp in weak_kps
        ]
    })


@teacher_bp.route('/api/teacher/class/overview', methods=['GET'])
@login_required
def api_class_overview():
    """API: 班级整体概览数据"""
    # 学生总数
    total = User.query.filter(User.is_admin == False).count()

    # 各等级人数和学科分布（基于画像+测评）
    level_dist, subject_dist = _get_all_students_level_distribution()

    # 平均学习积分
    sample_users = User.query.filter(User.is_admin == False).limit(50).all()
    avg_score = sum(BehaviorTracker.calculate_learning_score(u.id) for u in sample_users) / len(sample_users) if sample_users else 0

    # 今日活跃
    today = datetime.now().date()
    active_today = LearningBehavior.query.filter(
        sa_func.date(LearningBehavior.created_at) == today
    ).distinct(LearningBehavior.user_id).count()

    return jsonify({
        'total_students': total,
        'level_distribution': {f"level_{l}": c for l, c in level_dist.items() if l},
        'subject_distribution': subject_dist,
        'average_learning_score': round(avg_score, 1),
        'active_today': active_today
    })
