"""
A3赛道 - 智学领航 个性化学习多智能体系统
"""
import os, sys, json, re, random, hashlib, time, requests, base64, hmac, urllib.parse, logging
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from fpdf import FPDF
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, g, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import json as _json_module

from flask_cors import CORS
from werkzeug.security import generate_password_hash

from models import db, User, Assessment, ResourceHistory, LearningPath, TutorSession, Evaluation, ProfileConversation, GeneratedResource, LearningBehavior, EvaluationReport, LearningPlan, ContentSafetyLog, AsyncTask, KnowledgePoint, WrongQuestion, init_db
from config import Config, LEVELS, DIMENSIONS, RESOURCE_TYPES, SUBJECTS
from evaluation_engine import SafetyFilter, BehaviorTracker, ProgressTracker, EVAL_DIMENSIONS
from agents.generator_agents import trap_exam_generator
from agents.subject_mapper import resolve_subject, resolve_subject_for_display
from llm_client import spark_chat, load_spark_config, volc_video_enabled, volc_video_submit, volc_video_query, evaluate_python_code
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from utils import (
    call_llm, get_weakness_points, calculate_memory_temperature, get_temperature_status,
    check_memory_temperature, extract_knowledge_points, add_or_update_knowledge_point,
    update_knowledge_point_remind_date, generate_stt_signature, stt_recognize,
    get_student_profile_context,
    record_wrong_question, get_wrong_questions, mark_wrong_question_mastered,
    get_wrong_question_stats, get_review_reminders,
)

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# 初始化数据库
init_db(app)

# 登录管理
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 注册蓝图模块
from routes import register_blueprints
register_blueprints(app)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 注入 fromjson 过滤器
@app.template_filter('fromjson')
def fromjson_filter(value):
    if isinstance(value, str):
        return _json_module.loads(value)
    return value

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 为所有已登录模板注入学习流程信息
@app.before_request
def inject_flow_context():
    if current_user.is_authenticated:
        uid = current_user.id
        completed = []
        evidence = {}

        # ① 对话画像：必须 is_complete=True
        try:
            cp = ProfileConversation.query.filter_by(user_id=uid, is_complete=True)\
                .order_by(ProfileConversation.updated_at.desc()).first()
            if cp and cp.profile_data:
                completed.append('profile')
                evidence['profile'] = True
        except Exception:
            pass

        # ② 入学测评：必须有实际分数（total_score 非空），或画像已完成（画像可替代测评）
        try:
            asmnt = Assessment.query.filter(
                Assessment.user_id == uid,
                Assessment.total_score.isnot(None)
            ).order_by(Assessment.created_at.desc()).first()
            if asmnt:
                completed.append('assessment')
                evidence['assessment'] = True
            elif 'profile' in evidence:
                # 画像完成可替代测评
                completed.append('assessment')
                evidence['assessment'] = True
        except Exception:
            if 'profile' in evidence:
                completed.append('assessment')
                evidence['assessment'] = True

        # ③ 学习资源：必须有 ≥2 条资源历史记录（或有生成的资源）
        try:
            res_count = ResourceHistory.query.filter_by(user_id=uid).count()
            gen_count = GeneratedResource.query.filter_by(user_id=uid).count()
            if res_count >= 2 or gen_count >= 1:
                completed.append('resources')
                evidence['resources'] = True
        except Exception:
            pass

        # ④ 路径规划：必须有一条活跃的学习路径
        try:
            lp = LearningPath.query.filter_by(user_id=uid, is_active=True).first()
            if lp and lp.path_data:
                completed.append('path')
                evidence['path'] = True
        except Exception:
            pass

        # ⑤ 智能辅导：至少有 1 条有回答的辅导会话（证明真正使用过）
        try:
            tutor_sessions = TutorSession.query.filter(
                TutorSession.user_id == uid,
                TutorSession.answer.isnot(None)
            ).count()
            if tutor_sessions >= 1:
                completed.append('tutor')
                evidence['tutor'] = True
        except Exception:
            pass

        # ⑥ 效果评估：必须有带评分的评估记录
        try:
            ev = Evaluation.query.filter(
                Evaluation.user_id == uid,
                Evaluation.overall_score.isnot(None)
            ).order_by(Evaluation.created_at.desc()).first()
            if ev:
                completed.append('evaluate')
                evidence['evaluate'] = True
            else:
                evr = EvaluationReport.query.filter(
                    EvaluationReport.user_id == uid,
                    EvaluationReport.overall_score.isnot(None)
                ).order_by(EvaluationReport.created_at.desc()).first()
                if evr:
                    completed.append('evaluate')
                    evidence['evaluate'] = True
        except Exception:
            pass

        g.completed_steps = completed
        g.step_evidence = evidence

        # ===== 定时复习提醒：每次请求自动检查濒危知识点和错题 =====
        try:
            from datetime import date
            today = date.today()
            reminder_key = f'reminder_checked_{today}'
            if session.get(reminder_key) != str(uid):
                reminders = get_review_reminders(uid)
                if reminders['summary']['total'] > 0:
                    g.review_reminders = reminders
                session[reminder_key] = str(uid)
        except Exception as e:
            logger.debug(f"复习提醒检查失败: {e}")
    else:
        g.completed_steps = []
        g.step_evidence = {}

def get_profile_boat_status(user_id):
    """
    计算小船的等级（形态）和学习积分（位置）。
    - 形态等级：来源于画像分析结果（profile_data.level），画像未完成时用 LearningPlan.current_level
    - 学习积分：来源于 BehaviorTracker 累加的学习积分，任何学习行为都会增加积分

    返回: dict {
        'level_id': 1~4 (船的形态等级)
        'learning_score': 0~100+ (船的前进积分)
        'source': str (说明数据来源)
    }
    """
    import json as _json

    # 1) 学习积分（位置）：BehaviorTracker 累加积分
    try:
        from evaluation_engine import BehaviorTracker
        learning_score = BehaviorTracker.calculate_learning_score(user_id)
    except Exception:
        learning_score = 0

    # 2) 形态等级：优先取画像评估的 level
    level_id = 1
    source = 'default'

    # 先看画像评估的等级
    cp = ProfileConversation.query.filter_by(
        user_id=user_id, is_complete=True
    ).order_by(ProfileConversation.updated_at.desc()).first()

    if cp and cp.profile_data:
        try:
            profile = _json.loads(cp.profile_data) if isinstance(cp.profile_data, str) else cp.profile_data
            profile_level = int(profile.get('level', 0))
            if 1 <= profile_level <= 4:
                level_id = profile_level
                source = 'profile_analysis'
        except Exception:
            pass

    # 如果画像没有有效 level，用 LearningPlan 的当前等级
    if source == 'default':
        try:
            active_plan = LearningPlan.query.filter_by(
                user_id=user_id, is_active=True
            ).order_by(LearningPlan.updated_at.desc()).first()
            if active_plan and active_plan.current_level:
                level_id = active_plan.current_level
                source = 'learning_plan'
        except Exception:
            pass

    # 如果还有问题，用最近的测评
    if source == 'default':
        try:
            latest_asmt = Assessment.query.filter_by(
                user_id=user_id
            ).order_by(Assessment.created_at.desc()).first()
            if latest_asmt:
                level_id = latest_asmt.level_id
                source = 'assessment'
        except Exception:
            pass

    return {
        'level_id': level_id,
        'learning_score': learning_score,
        'source': source
    }

@app.context_processor
def inject_flow_vars():
    """注入全局模板变量：完成步骤 + 当前等级 + 学习积分（用于小船位置）"""
    result = {'completed_steps': getattr(g, 'completed_steps', [])}
    
    # 注入复习提醒（用于全局通知栏）
    review_reminders = getattr(g, 'review_reminders', None)
    if review_reminders:
        result['review_reminders'] = review_reminders
    
    # 注入当前等级和学习积分（用于侧边栏小船显示和位置）
    # 形态=画像分析等级，位置=BehaviorTracker学习积分
    if current_user.is_authenticated:
        try:
            boat_status = get_profile_boat_status(current_user.id)
            result['current_level_id'] = boat_status['level_id']
            result['learning_score'] = boat_status['learning_score']
            level_names = {1: '基础', 2: '中等', 3: '高级', 4: '大神'}
            result['current_level_name'] = level_names.get(boat_status['level_id'], '基础')

            # 计算小船位置百分比（10% ~ 88%），前端直接使用此值
            score = boat_status['learning_score']
            if score <= 0:
                result['boat_position_percent'] = 10.0
            elif score <= 15:
                result['boat_position_percent'] = round(10 + (score / 15) * 15, 1)
            elif score <= 40:
                result['boat_position_percent'] = round(25 + ((score - 15) / 25) * 25, 1)
            elif score <= 80:
                result['boat_position_percent'] = round(50 + ((score - 40) / 40) * 25, 1)
            else:
                result['boat_position_percent'] = round(min(75 + ((score - 80) / 40) * 13, 88), 1)
        except Exception:
            result['current_level_id'] = 1
            result['learning_score'] = 0
            result['current_level_name'] = '基础'
            result['boat_position_percent'] = 10.0
    else:
        result['current_level_id'] = 1
        result['learning_score'] = 0
        result['current_level_name'] = '基础'
        result['boat_position_percent'] = 10.0
    
    return result

# ===== 导入原来的推荐引擎 =====
from recommender import SCHOOL_TIERS, match_school_tier, recommend
from agents.profiling_agent import ProfilingAgent
from agents.resource_agent import ResourceAgent
from agents.path_planning_agent import PathPlanningAgent
from agents.tutor_agent import TutorAgent
from agents.assessment_agent import AssessmentAgent
profiling_agent = ProfilingAgent()
resource_agent = ResourceAgent()
path_agent = PathPlanningAgent()
tutor_agent = TutorAgent()
assess_agent = AssessmentAgent()
# ===== 新增：多智能体资源生成 + 对话画像 =====
from agents.generator_agents import generator_coordinator, profile_builder

# ===== 新增：对话式画像构建 =====

@app.route('/profile')
@login_required
def profile_building():
    """对话式画像构建页面"""
    return render_template('profile_builder.html', current_step='profile')

@app.route('/api/profile/start', methods=['POST'])
@login_required

def api_profile_start():
    """开始/继续对话画像（支持LLM智能对话模式）"""
    # 查找未完成的对话
    active = ProfileConversation.query.filter_by(
        user_id=current_user.id, is_complete=False
    ).order_by(ProfileConversation.updated_at.desc()).first()

    if active:
        conv = json.loads(active.conversation) if active.conversation else []
        stage = active.stage
    else:
        active = ProfileConversation(user_id=current_user.id)
        db.session.add(active)
        db.session.commit()
        conv = []
        stage = "greeting"

    # 如果已有完成的画像数据，直接返回
    if active.profile_data and stage in ('complete', 'completed'):
        try:
            profile = json.loads(active.profile_data) if isinstance(active.profile_data, str) else active.profile_data
        except Exception:
            profile = {}
        return jsonify({
            "conversation_id": active.id,
            "stage": 'complete',
            "is_complete": True,
            "profile": profile
        })

    # 如果是 chatting 模式（LLM动态对话中），从历史中恢复最后一个问题
    if stage == "chatting" and conv:
        last_entry = conv[-1] if conv else {}
        last_question = last_entry.get("question", "请继续描述你的学习情况")
        return jsonify({
            "conversation_id": active.id,
            "stage": "chatting",
            "question": last_question,
            "options": [],
            "history": conv,
            "is_complete": False
        })

    # 获取当前阶段问话（兼容旧阶段流程）
    q_data = profile_builder.get_question_for_stage(stage)

    # 如果是新对话且在greeting阶段，只显示问候语
    if stage == "greeting" and not bool(conv):
        greeting_info = profile_builder.stage_questions.get("greeting", {})
        return jsonify({
            "conversation_id": active.id,
            "stage": stage,
            "question": greeting_info.get("question", "你好！👋"),
            "options": [],
            "history": conv,
            "is_complete": False
        })

    return jsonify({
        "conversation_id": active.id,
        "stage": stage,
        "question": q_data.get("question", ""),
        "options": profile_builder._get_fallback_options(stage) if stage not in ('greeting', 'summary', 'complete') else [],
        "history": conv,
        "is_complete": q_data.get("is_complete", False)
    })

@app.route('/api/profile/chat', methods=['POST'])
@login_required
def api_profile_chat():
    """处理画像对话（LLM驱动智能对话模式）"""
    data = request.get_json()
    conv_id = data.get('conversation_id')
    answer = data.get('answer', '')

    conv = ProfileConversation.query.get_or_404(conv_id)
    if conv.user_id != current_user.id:
        return jsonify({"error": "无权限"}), 403

    # 获取当前对话历史
    history = json.loads(conv.conversation) if conv.conversation else []
    current_stage = conv.stage

    # 记录当前轮：把上一轮AI问题 + 用户回答存入历史
    q_data = profile_builder.get_question_for_stage(current_stage) if current_stage in profile_builder.STAGES else {"question": ""}
    # 如果是 chatting 模式（LLM动态对话），上一轮问题已存在history最后一条的question中
    last_question = ""
    if history and history[-1].get("stage") == "chatting":
        last_question = history[-1].get("question", "")
    else:
        last_question = q_data.get("question", "")

    history.append({
        "stage": current_stage if current_stage != "chatting" else "chatting",
        "question": last_question,
        "answer": answer,
        "timestamp": datetime.utcnow().isoformat()
    })

    # 调用 LLM 驱动的智能对话
    result = profile_builder.chat_with_llm(history, answer)

    # 强制执行 MIN_ROUNDS：即使 LLM 想提前结束，也必须保证6个维度的问题都问过
    answered_rounds = len([c for c in history if c.get("answer")])
    if result.get("action") == "complete" and answered_rounds < profile_builder.MIN_ROUNDS:
        # LLM 提前结束，强制走降级方案继续提问（覆盖6个维度）
        result = profile_builder._fallback_ask(history, answer)

    conv.conversation = json.dumps(history)
    conv.updated_at = datetime.utcnow()

    if result.get("action") == "complete":
        # 画像构建完成
        profile = result["profile"]
        conv.profile_data = json.dumps(profile)
        conv.is_complete = True
        conv.stage = "complete"
        db.session.commit()

        # ===== 同步更新学习计划等级 + 增加学习积分（驱动小船变化）=====
        try:
            profile_level = profile.get("level", 1)
            profile_total_score = sum(profile.get("dimension_scores", {}).values()) / 8 if profile.get("dimension_scores") else 50
            profile_subject = profile.get("major", "") or resolve_subject(getattr(conv, 'subject', 'computer_science') or 'computer_science')

            # 1. 更新/创建 LearningPlan
            plan = LearningPlan.query.filter_by(
                user_id=current_user.id, is_active=True
            ).order_by(LearningPlan.updated_at.desc()).first()

            if plan:
                old_level = plan.current_level or 1
                plan.current_level = max(old_level, profile_level)  # 等级只升不降
                plan.subject = profile_subject or plan.subject
                plan.updated_at = datetime.utcnow()
            else:
                plan = LearningPlan(
                    user_id=current_user.id,
                    subject=profile_subject,
                    current_level=profile_level,
                    target_level=min(profile_level + 1, 4),
                    is_active=True,
                    started_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(plan)

            # 2. 增加学习行为记录（提升学习积分 → 小船位置移动）
            behavior = LearningBehavior(
                user_id=current_user.id,
                behavior_type='profile_complete',
                subject=profile_subject,
                score=profile_total_score,
                completion=100,
                detail=json.dumps({
                    'profile_level': profile_level,
                    'dimension_scores': profile.get('dimension_scores', {}),
                    'cognitive_style': profile.get('cognitive_style', ''),
                })
            )
            db.session.add(behavior)
            db.session.commit()
        except Exception as e:
            logger.error(f"[ProfileSync] 画像同步失败: {e}")
            db.session.rollback()

        return jsonify({
            "is_complete": True,
            "profile": profile,
            "boat_level": profile.get("level", 1),
            "message": "🎉 画像构建完成！小船已调整航向~"
        })
    else:
        # 继续对话
        next_question = result.get("question", "请继续描述你的学习情况")
        next_options = result.get("options", [])
        conv.stage = "chatting"
        db.session.commit()
        return jsonify({
            "is_complete": False,
            "stage": "chatting",
            "question": next_question,
            "options": next_options,
            "history": history,
            "detected_level": result.get("detected_level"),
            "round_count": len([c for c in history if c.get("answer")])
        })

@app.route('/api/profile/result')
@login_required
def api_profile_result():
    """获取最新画像结果"""
    latest = ProfileConversation.query.filter_by(
        user_id=current_user.id, is_complete=True
    ).order_by(ProfileConversation.updated_at.desc()).first()
    
    if not latest:
        return jsonify({"has_profile": False})
    
    return jsonify({
        "has_profile": True,
        "profile": json.loads(latest.profile_data) if latest.profile_data else {},
        "created_at": latest.updated_at.strftime("%Y-%m-%d %H:%M")
    })


# ===== 新增：多智能体资源生成 =====

@app.route('/resource-gen')
@login_required
def resource_generation():
    """多智能体资源生成页面"""
    subjects_json = json.dumps(SUBJECTS, ensure_ascii=False)
    return render_template('resource_gen.html', current_step='resources', subjects=SUBJECTS, subjects_json=subjects_json)

@app.route('/ai-video')
@login_required
def ai_video_page():
    """AI 智能视频生成独立页面"""
    subjects_json = json.dumps(SUBJECTS, ensure_ascii=False)
    return render_template('ai_video.html', current_step='ai_video', subjects=SUBJECTS, subjects_json=subjects_json)

@app.route('/code-practice')
@login_required
def code_practice_page():
    """Python 代码练习与 AI 批改页面"""
    return render_template('code_practice.html', current_step='code_practice')

@app.route('/api/generate/context', methods=['POST'])
@login_required
def api_parse_request():
    """解析学生需求，提取生成上下文"""
    data = request.get_json()
    request_text = data.get('request', '')
    subject = resolve_subject(data.get('subject', 'computer_science'))
    level = data.get('level', 2)
    
    context = generator_coordinator.parse_student_request(request_text)
    context['subject'] = subject
    context['subject_name'] = SUBJECTS.get(subject, subject)
    context['level'] = level
    
    # 注入学生画像上下文：同一个需求，不同画像的学生得不同级别
    student_profile = get_student_profile_context(current_user.id)
    if student_profile.get('has_profile'):
        context['student_profile'] = student_profile
        context['_profile_level_hint'] = student_profile.get('level', level)
    
    return jsonify({"context": context})

@app.route('/api/generate/all', methods=['POST'])
@login_required
def api_generate_all():
    """生成全套学习资源（5种类型）"""
    data = request.get_json()
    context = data.get('context', {})
    
    if not context.get('subject'):
        context['subject'] = 'computer_science'
    if not context.get('subject_name'):
        context['subject_name'] = SUBJECTS.get(context['subject'], context['subject'])
    if not context.get('level'):
        context['level'] = 2
    if not context.get('topic'):
        context['topic'] = context['subject_name']
    
    # 注入学生画像上下文：不同画像的学生获得不同资源
    student_profile = get_student_profile_context(current_user.id)
    if student_profile.get('has_profile'):
        context['student_profile'] = student_profile
        # 如果画像等级更高，提升资源难度等级
        if student_profile.get('level', 1) > context.get('level', 1):
            context['level'] = student_profile['level']
        # 合并薄弱点
        profile_weak_points = student_profile.get('weak_points', [])
        if profile_weak_points:
            existing = set(context.get('weak_points', []))
            for w in profile_weak_points:
                if w not in existing:
                    context.setdefault('weak_points', []).append(w)
                    existing.add(w)
    
    result = generator_coordinator.generate_all(context)
    
    # 保存到数据库
    for rtype, resource in result.get('resources', {}).items():
        gr = GeneratedResource(
            user_id=current_user.id,
            subject=context['subject'],
            resource_type=rtype,
            title=resource.get('title', ''),
            content=json.dumps(resource),
            context=json.dumps(context),
        )
        db.session.add(gr)
        
        resource_text = f"{resource.get('title', '')} {resource.get('content', '')}"
        knowledge_points = extract_knowledge_points(resource_text, context['subject'])
        for kp in knowledge_points:
            add_or_update_knowledge_point(current_user.id, context['subject'], kp[0])
    db.session.commit()
    
    return jsonify(result)

@app.route('/api/generate/type', methods=['POST'])
@login_required
def api_generate_type():
    """生成指定类型的资源"""
    data = request.get_json()
    context = data.get('context', {})
    resource_type = data.get('type', 'document')
    
    if not context.get('subject'):
        context['subject'] = 'computer_science'
    if not context.get('subject_name'):
        context['subject_name'] = SUBJECTS.get(context['subject'], context['subject'])
    if not context.get('level'):
        context['level'] = 2
    if not context.get('topic'):
        context['topic'] = context['subject_name']
    
    # 注入学生画像上下文
    student_profile = get_student_profile_context(current_user.id)
    if student_profile.get('has_profile'):
        context['student_profile'] = student_profile
        if student_profile.get('level', 1) > context.get('level', 1):
            context['level'] = student_profile['level']
        profile_weak_points = student_profile.get('weak_points', [])
        if profile_weak_points:
            existing = set(context.get('weak_points', []))
            for w in profile_weak_points:
                if w not in existing:
                    context.setdefault('weak_points', []).append(w)
                    existing.add(w)
    
    result = generator_coordinator.generate_type(resource_type, context)
    
    if result.get('success'):
        resource = result['resource']
        gr = GeneratedResource(
            user_id=current_user.id,
            subject=context['subject'],
            resource_type=resource_type,
            title=resource.get('title', ''),
            content=json.dumps(resource),
            context=json.dumps(context),
        )
        db.session.add(gr)
        db.session.commit()

    return jsonify(result)


# ===== AI视频生成接口（火山引擎豆包视频生成模型） =====

@app.route('/api/video/status')
@login_required
def api_video_status():
    """查询火山引擎视频生成API是否可用"""
    return jsonify({
        "enabled": volc_video_enabled(),
        "provider": "volc_engine",
        "model": os.environ.get('VOLC_VIDEO_MODEL', 'doubao-seedance-1-0-pro-250528'),
        "docs_url": "https://www.volcengine.com/docs/82379",
        "key_url": "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey"
    })


@app.route('/api/video/generate', methods=['POST'])
@login_required
def api_video_generate():
    """提交AI视频生成任务（异步）

    请求体:
    {
        "prompt": "视频生成提示词",
        "duration": 5,
        "resolution": "720p",
        "aspect_ratio": "16:9"
    }
    """
    data = request.get_json() or {}
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return jsonify({"success": False, "error": "提示词不能为空"}), 400

    if not volc_video_enabled():
        return jsonify({
            "success": False,
            "error": "AI视频生成功能未启用。请在 .env 文件中配置 VOLC_AK_ID（火山方舟API Key）。",
            "guide": "获取密钥地址：https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey",
            "docs": "https://www.volcengine.com/docs/82379"
        }), 503

    duration = int(data.get('duration', 5))
    resolution = data.get('resolution', '720p')
    aspect_ratio = data.get('aspect_ratio', '16:9')

    result = volc_video_submit(
        prompt=prompt,
        duration=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio
    )
    return jsonify(result)


@app.route('/api/video/task/<task_id>')
@login_required
def api_video_task(task_id):
    """查询视频生成任务状态"""
    if not task_id or not re.match(r'^[a-zA-Z0-9\-]+$', task_id):
        return jsonify({"success": False, "error": "无效的任务ID"}), 400

    result = volc_video_query(task_id)
    return jsonify(result)


@app.route('/api/video/script', methods=['POST'])
@login_required
def api_video_script():
    """生成AI视频脚本（不需要视频API密钥）"""
    data = request.get_json() or {}
    subject = data.get('subject', 'computer_science')
    topic = (data.get('topic') or '').strip()
    level = int(data.get('level', 2))

    if not topic:
        return jsonify({"success": False, "error": "请提供主题"}), 400

    try:
        from agents.generator_agents import VideoAgent
        agent = VideoAgent()
        result = agent.generate({
            "subject": subject,
            "subject_name": SUBJECTS.get(subject, subject),
            "topic": topic,
            "level": level,
        })
        return jsonify({
            "success": True,
            "script": result.get('ai_video_script', {}),
            "videos": result.get('videos', []),
            "ai_video_enabled": result.get('ai_video_enabled', False),
        })
    except Exception as e:
        logger.error(f"[VideoScript] 脚本生成失败: {e}")
        return jsonify({"success": False, "error": f"脚本生成失败: {e}"}), 500


# ===== Python代码AI批改接口 =====

@app.route('/api/case/evaluate_code', methods=['POST'])
@login_required
def api_case_evaluate_code():
    """AI批改学生Python代码

    请求体:
    {
        "code": "学生代码",
        "task_description": "题目要求",
        "reference_answer": "参考答案（可选）"
    }

    返回:
    {
        "success": true,
        "score": 85,
        "correctness": "correct|partial|incorrect",
        "overall_comment": "整体评价",
        "issues": [{"line": 5, "severity": "high", "issue": "...", "suggestion": "..."}]
    }
    """
    data = request.get_json() or {}
    code = data.get('code', '')
    task_desc = data.get('task_description', '')
    ref_answer = data.get('reference_answer', '')

    if not code or not code.strip():
        return jsonify({"success": False, "error": "代码不能为空"}), 400

    # 限制代码长度，防止滥用
    if len(code) > 10000:
        return jsonify({"success": False, "error": "代码过长（最大10000字符）"}), 400

    result = evaluate_python_code(
        student_code=code,
        task_description=task_desc,
        reference_answer=ref_answer
    )
    return jsonify(result)


@app.route('/generate_trap_exam', methods=['POST'])
@login_required
def generate_trap_exam():
    """
    生成克星题 - 针对学生认知弱点生成陷阱题目
    
    请求参数：
    - student_id: 学生ID（可选，默认使用当前登录用户）
    - subject: 学科key（前端传递，支持自定义学科）
    - subject_name: 学科名称（前端传递，支持自定义学科）
    
    返回：
    - questions: 题目列表（含陷阱说明）
    """
    data = request.get_json()
    student_id = data.get('student_id', current_user.id)
    
    # 验证权限 - 允许自己访问自己的数据，或管理员访问所有数据
    if student_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权限访问该学生数据"}), 403
    
    # 获取前端传递的学科信息（优先使用）
    subject = resolve_subject(data.get('subject', 'computer_science'))
    subject_name = data.get('subject_name', SUBJECTS.get(subject, subject))
    
    # 支持指定弱点名称以生成针对性题目
    focus_weakness = data.get('weakness', '').strip()
    
    # 使用共享的 get_weakness_points 从数据库获取认知弱点数据
    weak_points = get_weakness_points(student_id)
    
    # 如果指定了弱点名称，优先使用该弱点
    if focus_weakness:
        # 将指定弱点放在最前面
        filtered = [w for w in weak_points if focus_weakness.lower() in w.lower()]
        if filtered:
            weak_points = filtered + [w for w in weak_points if w not in filtered]
    
    # 注入学生画像上下文：克星题也针对画像薄弱维度
    student_profile = get_student_profile_context(student_id)
    if student_profile.get('has_profile'):
        profile_weak_points = student_profile.get('weak_points', [])
        if profile_weak_points:
            dim_to_weakness = {
                "application": "缺乏实际应用能力",
                "understanding": "概念理解深度不够",
                "analysis": "分析评价能力不足",
                "creativity": "创新思维能力弱",
                "knowledge": "基础知识不扎实",
                "self_learning": "自主学习效率低",
                "pace": "学习节奏把握不好",
                "cognitive": "认知层次偏低"
            }
            for dim in profile_weak_points:
                desc = dim_to_weakness.get(dim, f"在{dim}方面需要加强")
                if desc not in weak_points:
                    weak_points.append(desc)
    
    # 调用 TrapExamGenerator 生成题目
    context = {
        "weak_points": weak_points,
        "subject": subject,
        "subject_name": subject_name,
        "focus_weakness": focus_weakness,
        "student_profile": student_profile
    }
    
    result = trap_exam_generator.generate(context)
    
    return jsonify({
        "success": True,
        "questions": result.get("questions", []),
        "title": result.get("title", ""),
        "metadata": result.get("metadata", {}),
        "weak_points_count": len(weak_points)
    })


@app.route('/api/generated/list')
@login_required
def api_generated_list():
    """获取已生成的资源列表"""
    rtype = request.args.get('type')
    raw_subject = request.args.get('subject')
    subject = resolve_subject(raw_subject) if raw_subject else None
    
    query = GeneratedResource.query.filter_by(user_id=current_user.id)
    if rtype:
        query = query.filter_by(resource_type=rtype)
    if subject:
        query = query.filter_by(subject=subject)
    
    resources = query.order_by(GeneratedResource.created_at.desc()).limit(50).all()
    
    return jsonify([{
        "id": r.id,
        "type": r.resource_type,
        "title": r.title,
        "subject": r.subject,
        "created_at": r.created_at.strftime("%m-%d %H:%M"),
        "is_favorite": r.is_favorite
    } for r in resources])

@app.route('/api/generated/view/<int:rid>')
@login_required
def api_generated_view(rid):
    """查看生成的资源详情"""
    resource = GeneratedResource.query.get_or_404(rid)
    if resource.user_id != current_user.id:
        return jsonify({"error": "无权限"}), 403
    
    # 记录阅读行为，自动更新画像等级
    try:
        BehaviorTracker.log(
            user_id=current_user.id,
            subject=resource.subject,
            behavior_type='read_resource',
            resource_type=resource.resource_type,
            resource_id=resource.id,
            time_spent=60,
            completion=50,
        )
    except Exception:
        pass
    
    return jsonify({
        "id": resource.id,
        "type": resource.resource_type,
        "title": resource.title,
        "subject": resource.subject,
        "content": json.loads(resource.content) if resource.content else {},
        "created_at": resource.created_at.strftime("%Y-%m-%d %H:%M"),
        "is_favorite": resource.is_favorite
    })

@app.route('/api/generated/favorite/<int:rid>', methods=['POST'])
@login_required
def api_toggle_favorite(rid):
    resource = GeneratedResource.query.get_or_404(rid)
    if resource.user_id != current_user.id:
        return jsonify({"error": "无权限"}), 403
    resource.is_favorite = not resource.is_favorite
    db.session.commit()
    return jsonify({"is_favorite": resource.is_favorite})

# ================================================================
# 路由 - 页面
# ================================================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_bp.admin_panel'))
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_bp.admin_panel'))
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_bp.admin_panel'))
            return redirect(url_for('dashboard'))
        flash('用户名或密码错误', 'error')
        return redirect(url_for('index'))
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if not username or not password:
            flash('用户名和密码不能为空', 'error')
            return render_template('register.html')
        
        if password != confirm:
            flash('两次密码输入不一致', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return render_template('register.html')
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功，请登录', 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    recent_assessment = Assessment.query.filter_by(user_id=current_user.id).order_by(Assessment.created_at.desc()).first()
    recent_eval = Evaluation.query.filter_by(user_id=current_user.id).order_by(Evaluation.created_at.desc()).first()
    tutor_count = TutorSession.query.filter_by(user_id=current_user.id).count()
    resource_count = ResourceHistory.query.filter_by(user_id=current_user.id).count()
    
    # 进步趋势
    subject_for_progress = recent_assessment.subject if recent_assessment else "computer_science"
    try:
        trend = assess_agent.get_progress(current_user.id, subject_for_progress)
    except Exception:
        trend = None
    
    # 获取当前等级（只基于对话画像，与小船保持一致）
    try:
        boat_status = get_profile_boat_status(current_user.id)
        current_level_id = boat_status['level_id']
        level_names = {1: '基础', 2: '中等', 3: '高级', 4: '大神'}
        current_level_name = level_names.get(current_level_id, '基础')
    except Exception:
        current_level_id = 1
        current_level_name = '基础'
    
    return render_template('dashboard.html', current_step='dashboard', 
                         recent_assessment=recent_assessment,
                         recent_eval=recent_eval,
                         tutor_count=tutor_count,
                         resource_count=resource_count,
                         trend=trend,
                         levels=LEVELS,
                         subjects=SUBJECTS,
                         current_level_id=current_level_id,
                         current_level_name=current_level_name)

@app.route('/assessment')
@login_required
def assessment():
    return render_template('assessment.html', current_step='assessment', subjects=SUBJECTS, school_tiers=SCHOOL_TIERS)

@app.route('/resources')
@login_required
def resources():
    subjects_json = json.dumps(SUBJECTS, ensure_ascii=False)
    return render_template('resources.html', current_step='resources', subjects=SUBJECTS, levels=LEVELS, subjects_json=subjects_json)

@app.route('/path')
@login_required
def path():
    return render_template('path.html', current_step='path', subjects=SUBJECTS, levels=LEVELS)




@app.route('/trap_exam')
@login_required
def trap_exam():
    """
    错题攻克页面 - 独立的克星题生成功能入口
    
    支持两种模式：
    1. 未选择学科：显示学科选择界面
    2. 已选择学科：显示弱点分析和生成按钮
    
    URL参数：
    - subject: 学科key
    - name: 学科名称（支持自定义学科）
    """
    selected_subject = resolve_subject(request.args.get('subject'))
    selected_subject_name = request.args.get('name')
    
    # 如果选择了学科，获取该学生在该学科的薄弱点数量
    subject_stats = {}
    weak_points = []
    weak_points_count = 0
    
    if selected_subject:
        # 使用共享的 get_weakness_points 从数据库获取认知弱点数据
        weak_points = get_weakness_points(current_user.id)
        weak_points_count = len(weak_points)
    
    # 学科统计信息（不显示随机的弱点数量）
    for key in SUBJECTS.keys():
        subject_stats[key] = {}
    
    # 学科图标映射
    subject_icons = {
        'computer_science': '💻', 'ai': '🤖', 'data_science': '📊', 
        'software_engineering': '🔧', 'electronic': '⚡', 'math': '📐',
        'english': '🌍', 'finance': '💰', 'law': '⚖️', 'psychology': '🧠',
        'education': '📚', 'art_design': '🎨'
    }
    
    return render_template('trap_exam.html',
        subjects=SUBJECTS,
        subject_icons=subject_icons,
        subject_stats=subject_stats,
        selected_subject=selected_subject,
        selected_subject_name=selected_subject_name,
        weak_points=weak_points,
        weak_points_count=weak_points_count
    )

# ================================================================
# 记忆温度计相关函数
# ================================================================


# ================================================================
# API 路由
# ================================================================

@app.route('/api/memory_temperature', methods=['GET'])
@login_required
def api_memory_temperature():
    """
    获取当前用户的记忆温度数据
    
    返回：
    - knowledge_points: 知识点温度列表
    - summary: 统计摘要（各状态数量）
    """
    points = check_memory_temperature(current_user.id)
    
    # 统计各状态数量
    summary = {
        "hot": 0,
        "warm": 0,
        "cold": 0,
        "critical": 0,
        "total": len(points)
    }
    for point in points:
        level = point.get("level", "cold")
        if level in summary:
            summary[level] += 1
    
    return jsonify({
        "success": True,
        "knowledge_points": points,
        "summary": summary
    })

@app.route('/api/memory_temperature/refresh', methods=['POST'])
@login_required
def api_refresh_knowledge_point():
    """
    刷新知识点（标记为已学习，重置记忆温度，提升掌握程度）
    
    请求参数：
    - point_id: 知识点ID
    """
    data = request.get_json()
    point_id = data.get('point_id')
    
    point = KnowledgePoint.query.get(point_id)
    if not point or point.user_id != current_user.id:
        return jsonify({"error": "知识点不存在或无权访问"}), 404
    
    point.update_mastery(min(1.0, point.mastery_level * 100 + 10))
    db.session.commit()
    
    return jsonify({"success": True})

@app.route('/api/memory_temperature/remind', methods=['POST'])
@login_required
def api_memory_temperature_remind():
    """
    获取需要提醒的濒危知识点（一天内未提醒过的）
    
    返回：
    - critical_points: 需要提醒的濒危知识点列表
    """
    from datetime import date
    
    today = date.today()
    points = KnowledgePoint.query.filter(
        KnowledgePoint.user_id == current_user.id,
        (KnowledgePoint.last_remind_date != today) | (KnowledgePoint.last_remind_date.is_(None))
    ).all()
    
    critical_points = []
    for point in points:
        temperature = calculate_memory_temperature(point.last_study_time, point.mastery_level)
        if temperature < 30:
            # 更新提醒日期，确保一天内只提醒一次
            point.last_remind_date = today
            db.session.add(point)
            
            # 获取可读的学科名称
            subject_name = SUBJECTS.get(point.subject, point.subject)
            
            critical_points.append({
                "id": point.id,
                "name": point.name,
                "subject": point.subject,
                "subject_name": subject_name,
                "temperature": round(temperature, 1)
            })
    
    # 提交数据库更新
    db.session.commit()
    
    return jsonify({
        "success": True,
        "critical_points": critical_points
    })

@app.route('/memory_health')
@login_required
def memory_health():
    """记忆健康度详情页面"""
    return render_template('memory_health.html',
        current_step='memory_health'
    )

# ===== 错题管理 API =====

@app.route('/api/wrong_questions', methods=['GET'])
@login_required
def api_wrong_questions():
    """获取当前用户的错题列表
    
    参数：
    - subject: 学科过滤（可选）
    - only_unmastered: 是否只返回未掌握 (1/0)
    """
    subject = request.args.get('subject')
    only_unmastered = request.args.get('only_unmastered', '0') == '1'
    
    questions = get_wrong_questions(current_user.id, subject=subject, only_unmastered=only_unmastered)
    stats = get_wrong_question_stats(current_user.id, subject=subject)
    
    return jsonify({
        "success": True,
        "questions": [{
            "id": wq.id,
            "subject": wq.subject,
            "question": wq.question,
            "correct_answer": wq.correct_answer,
            "user_answer": wq.user_answer,
            "question_type": wq.question_type,
            "knowledge_point": wq.knowledge_point,
            "difficulty": wq.difficulty,
            "source": wq.source,
            "is_mastered": wq.is_mastered,
            "review_count": wq.review_count,
            "created_at": wq.created_at.strftime("%Y-%m-%d %H:%M") if wq.created_at else None,
        } for wq in questions],
        "stats": stats,
    })


@app.route('/api/wrong_questions/<int:wq_id>/master', methods=['POST'])
@login_required
def api_master_wrong_question(wq_id):
    """标记错题为已掌握"""
    success = mark_wrong_question_mastered(wq_id, current_user.id)
    if not success:
        return jsonify({"error": "错题不存在或无权访问"}), 404
    return jsonify({"success": True})


@app.route('/api/wrong_questions/stats', methods=['GET'])
@login_required
def api_wrong_question_stats():
    """获取错题统计"""
    subject = request.args.get('subject')
    stats = get_wrong_question_stats(current_user.id, subject=subject)
    return jsonify({"success": True, "stats": stats})


@app.route('/api/review_reminders', methods=['GET'])
@login_required
def api_review_reminders():
    """手动获取复习提醒（用于前端主动检查）"""
    reminders = get_review_reminders(current_user.id)
    return jsonify({"success": True, "reminders": reminders})

@app.route('/api/assessment/questions', methods=['POST'])
@login_required
def api_get_questions():
    data = request.get_json()
    subject = resolve_subject(data.get('subject', 'computer_science'))
    questions = profiling_agent.generate_questions(subject)
    return jsonify({"questions": questions, "subject": subject})

@app.route('/api/assessment/submit', methods=['POST'])
@login_required
def api_submit_assessment():
    data = request.get_json()
    subject = resolve_subject(data.get('subject', 'computer_science'))
    answers = data.get('answers', {})
    school_tier = data.get('school_tier')
    
    result = profiling_agent.analyze_assessment(answers, subject, school_tier)
    
    # 保存测评记录
    assessment = Assessment(
        user_id=current_user.id,
        subject=subject,
        total_score=result["total_score"],
        level_id=result["level"]["id"],
        level_name=result["level"]["name"],
        dimension_scores=json.dumps(result["dimension_scores"]),
        answers=json.dumps(answers),
        feedback=result["feedback"],
    )
    db.session.add(assessment)
    db.session.commit()
    
    # 记录测评涉及的知识点到记忆温度计
    feedback = result.get("feedback", "")
    knowledge_points = extract_knowledge_points(feedback, subject)
    for kp in knowledge_points:
        add_or_update_knowledge_point(current_user.id, subject, kp[0])
    
    # ===== 记录错题到 WrongQuestion 表 =====
    try:
        # 从画像测评答案中识别低分项（自评分数<60的维度视为错题/薄弱点）
        if isinstance(answers, dict):
            for qid, answer in answers.items():
                if isinstance(answer, dict) and 'value' in answer:
                    score = answer.get('value', 0)
                    if isinstance(score, (int, float)) and score < 60:
                        # 低分项记录为错题
                        question_text = answer.get('text', f'测评题目{qid}') if isinstance(answer, dict) else f'测评题目{qid}'
                        record_wrong_question(
                            user_id=current_user.id,
                            subject=subject,
                            question=question_text[:500],
                            user_answer=f'自评: {score}分',
                            correct_answer='目标: 80分以上',
                            question_type='self_assessment',
                            knowledge_point=knowledge_points[0][0] if knowledge_points else None,
                            difficulty='medium' if score < 40 else 'easy',
                            source='assessment',
                        )
                elif isinstance(answer, (int, float)) and answer < 60:
                    record_wrong_question(
                        user_id=current_user.id,
                        subject=subject,
                        question=f'测评题目{qid}',
                        user_answer=f'得分: {answer}',
                        correct_answer='及格线: 60',
                        question_type='self_assessment',
                        knowledge_point=knowledge_points[0][0] if knowledge_points else None,
                        difficulty='medium' if answer < 40 else 'easy',
                        source='assessment',
                    )
    except Exception as e:
        logger.error(f"记录错题失败: {e}")
    
    # 记录学习行为
    try:
        BehaviorTracker.log(
            user_id=current_user.id,
            subject=subject,
            behavior_type='assessment',
            resource_type='quiz',
            score=result["total_score"],
            time_spent=300,
            completion=100,
            detail={'question_count': len(answers), 'level_id': result["level"]["id"]}
        )
    except Exception as e:
        logger.error(f"记录学习行为失败: {e}")
    
    return jsonify({
        "success": True,
        "assessment_id": assessment.id,
        "result": result
    })

@app.route('/api/assessment/latest', methods=['GET'])
@login_required
def api_latest_assessment():
    subject = resolve_subject(request.args.get('subject', 'computer_science'))
    assessment = Assessment.query.filter_by(
        user_id=current_user.id, subject=subject
    ).order_by(Assessment.created_at.desc()).first()
    
    if assessment:
        return jsonify({
            "has_assessment": True,
            "id": assessment.id,
            "total_score": assessment.total_score,
            "level_id": assessment.level_id,
            "level_name": assessment.level_name,
            "dimension_scores": json.loads(assessment.dimension_scores) if assessment.dimension_scores else {},
            "feedback": assessment.feedback,
            "created_at": assessment.created_at.strftime("%Y-%m-%d %H:%M")
        })
    
    # 没有入学测评记录时，检查画像是否已完成——画像可作为测评的替代
    from models import ProfileConversation
    import json as _json
    latest_profile = ProfileConversation.query.filter_by(
        user_id=current_user.id, is_complete=True
    ).order_by(ProfileConversation.updated_at.desc()).first()
    
    if latest_profile and latest_profile.profile_data:
        try:
            profile = _json.loads(latest_profile.profile_data) if isinstance(latest_profile.profile_data, str) else latest_profile.profile_data
            dim_scores = profile.get('dimension_scores', {})
            total_score = profile.get('level', 50) * 25  # level 1-4 映射到 25-100
            if dim_scores:
                scores_list = [v for v in dim_scores.values() if isinstance(v, (int, float))]
                if scores_list:
                    total_score = round(sum(scores_list) / len(scores_list))
            level_id = profile.get('level', 1)
            level_names = {1: '基础', 2: '中等', 3: '高等', 4: '大神'}
            return jsonify({
                "has_assessment": True,
                "from_profile": True,
                "id": latest_profile.id,
                "total_score": total_score,
                "level_id": level_id,
                "level_name": level_names.get(level_id, '基础'),
                "dimension_scores": dim_scores,
                "feedback": f"基于对话画像生成。综合评分{total_score}分，当前水平：{level_names.get(level_id, '基础')}。",
                "created_at": latest_profile.updated_at.strftime("%Y-%m-%d %H:%M") if latest_profile.updated_at else ""
            })
        except Exception as e:
            logger.warning(f"[AssessmentLatest] 画像数据解析失败: {e}")
    
    return jsonify({"has_assessment": False})

@app.route('/api/boat/status', methods=['GET'])
@login_required
def api_boat_status():
    """
    获取当前用户的小船状态（等级 + 学习积分 + 位置百分比）。
    - 形态等级：来源于画像分析结果（profile_data.level），画像未完成时用 LearningPlan.current_level
    - 学习积分：来源于 BehaviorTracker 累加积分，任何学习行为都会增加积分
    """
    try:
        boat_status = get_profile_boat_status(current_user.id)
        level_id = boat_status['level_id']
        learning_score = boat_status['learning_score']

        # 位置映射：学习积分 → 10% ~ 88%（积分越高，船越靠右）
        # Level 1 (0分): 10%, Level 2 (15分): 25%, Level 3 (40分): 50%, Level 4 (80分+): 75%~88%
        if learning_score <= 0:
            position_percent = 10.0
        elif learning_score <= 15:
            position_percent = round(10 + (learning_score / 15) * 15, 1)
        elif learning_score <= 40:
            position_percent = round(25 + ((learning_score - 15) / 25) * 25, 1)
        elif learning_score <= 80:
            position_percent = round(50 + ((learning_score - 40) / 40) * 25, 1)
        else:
            position_percent = round(min(75 + ((learning_score - 80) / 40) * 13, 88), 1)

        level_names = {1: '划艇', 2: '小帆船', 3: '大船', 4: '豪华游轮'}

        return jsonify({
            "level_id": level_id,
            "level_name": level_names.get(level_id, '划艇'),
            "learning_score": learning_score,
            "position_percent": position_percent,
            "source": boat_status['source'],
            "boat_types": {
                "1": {"name": "划艇", "size": "55x35", "desc": "初学者的小舟"},
                "2": {"name": "小帆船", "size": "75x50", "desc": "掌握基础，可以扬帆"},
                "3": {"name": "大船", "size": "95x65", "desc": "知识体系完整"},
                "4": {"name": "豪华游轮", "size": "120x80", "desc": "学霸级的航行者"}
            }
        })
    except Exception as e:
        logger.error(f"[BoatStatus] 获取船状态失败: {e}")
        return jsonify({"error": "获取失败", "level_id": 1, "learning_score": 0, "position_percent": 10}), 500

@app.route('/api/resources/recommend', methods=['POST'])
@login_required
def api_recommend_resources():
    data = request.get_json()
    subject = resolve_subject(data.get('subject', 'computer_science'))
    level_id = data.get('level_id', 1)
    school_tier = data.get('school_tier')
    
    resources = resource_agent.recommend(level_id, subject, school_tier)
    
    # 保存资源记录
    for r in resources:
        hist = ResourceHistory(
            user_id=current_user.id,
            subject=subject,
            resource_type=r.get("type", ""),
            title=r.get("title", ""),
            content=r.get("content", ""),
            source=r.get("source", ""),
            level=r.get("level", ""),
            level_id=level_id,
            tags=json.dumps(r.get("tags", []))
        )
        db.session.add(hist)
        
        # 记录资源涉及的知识点到记忆温度计
        resource_text = f"{r.get('title', '')} {r.get('content', '')}"
        knowledge_points = extract_knowledge_points(resource_text, subject)
        for kp in knowledge_points:
            add_or_update_knowledge_point(current_user.id, subject, kp)
    
    db.session.commit()
    
    # 记录学习行为
    try:
        BehaviorTracker.log(
            user_id=current_user.id,
            subject=subject,
            behavior_type='resource_recommend',
            resource_type='document',
            time_spent=60,
            detail={'resource_count': len(resources), 'level': level_id}
        )
    except Exception as e:
        logger.error(f"记录学习行为失败: {e}")
    
    return jsonify({"resources": resources, "count": len(resources)})

@app.route('/api/path/plan', methods=['POST'])
@login_required
def api_plan_path():
    data = request.get_json()
    subject = resolve_subject(data.get('subject', 'computer_science'))
    level_id = data.get('level_id', 1)
    dimension_scores = data.get('dimension_scores')
    
    path_result = path_agent.plan_path(level_id, subject, dimension_scores)
    
    # 将旧的活跃路径标记为非活跃
    LearningPath.query.filter_by(user_id=current_user.id, is_active=True).update({'is_active': False})
    
    # 保存新路径
    lp = LearningPath(
        user_id=current_user.id,
        subject=subject,
        path_data=json.dumps(path_result),
        is_active=True
    )
    db.session.add(lp)
    db.session.commit()
    
    return jsonify({"path": path_result})





@app.route('/api/user/stats', methods=['GET'])
@login_required
def api_user_stats():
    assessments = Assessment.query.filter_by(user_id=current_user.id).all()
    evaluations = Evaluation.query.filter_by(user_id=current_user.id).all()
    
    # 等级和学习积分（与小船保持一致）：等级=画像分析/LearningPlan，积分=BehaviorTracker累加
    boat_status = get_profile_boat_status(current_user.id)
    current_level_id = boat_status['level_id']
    learning_score = boat_status['learning_score']
    level_names = {1: '基础', 2: '中等', 3: '高级', 4: '大神'}
    latest_level = level_names.get(current_level_id, f'Level {current_level_id}')
    
    # 生成近 52 周（一整年）学习热力图数据（GitHub 风格）
    from datetime import date, timedelta
    today = date.today()
    # 找到最近的周日作为起始
    start_day = today - timedelta(days=today.weekday())
    weeks = 52
    days = []
    for w in range(weeks):
        for d in range(7):
            day = start_day - timedelta(weeks=weeks - 1 - w, days=6 - d)
            days.append(day)
    
    # 查询所有学习行为记录
    behaviors = LearningBehavior.query.filter(
        LearningBehavior.user_id == current_user.id
    ).all()
    # 统计每日学习强度
    day_counts = {}
    for b in behaviors:
        if b.created_at:
            d = b.created_at.date()
            day_counts[d] = day_counts.get(d, 0) + 1
    
    heatmap = []
    total_active = 0
    max_count = 1
    for d in days:
        count = day_counts.get(d, 0)
        if d > today:
            level = -1  # 未来
        elif count == 0:
            level = 0
        elif count <= 2:
            level = 1
        elif count <= 5:
            level = 2
        elif count <= 10:
            level = 3
        else:
            level = 4
        if level > 0:
            total_active += 1
            if count > max_count:
                max_count = count
        heatmap.append({
            'date': d.strftime('%Y-%m-%d'),
            'weekday': d.weekday(),
            'count': count,
            'level': level,
        })
    
    # 按周组织
    weeks_data = []
    for w in range(weeks):
        week_days = heatmap[w * 7:(w + 1) * 7]
        weeks_data.append(week_days)
    
    # 生成月份标签（用于X轴）
    month_labels = []
    for w_idx, week in enumerate(weeks_data):
        first_day = week[0]
        month = first_day['date'][5:7]
        month_name = f"{int(month)}月"
        if w_idx == 0 or month != weeks_data[w_idx - 1][0]['date'][5:7]:
            month_labels.append({
                'week_index': w_idx,
                'label': month_name
            })
    
    # 生成星期标签（用于Y轴）
    weekday_labels = ['一', '三', '五']
    
    # 最近 7 天学习统计
    recent = heatmap[-7:] if len(heatmap) >= 7 else heatmap
    recent_count = sum(1 for d in recent if d['level'] > 0)
    recent_total = sum(d['count'] for d in recent)
    
    # 计算连续学习天数
    streak = 0
    for d in reversed(heatmap):
        if d['level'] > 0:
            streak += 1
        elif d['date'] <= today.strftime('%Y-%m-%d'):
            break
    
    # 计算等级进度（基于 BehaviorTracker 的阈值：0→Lv1, 15→Lv2, 40→Lv3, 80→Lv4）
    bt_thresholds = [
        (1, 0, 14.9),
        (2, 15, 39.9),
        (3, 40, 79.9),
        (4, 80, float('inf')),
    ]
    current_range = next((r for r in bt_thresholds if r[0] == current_level_id), bt_thresholds[0])
    _, r_start, r_end = current_range
    if current_level_id >= 4:
        level_progress = 100
    else:
        level_progress = round(max(0, min(100, (learning_score - r_start) / (r_end - r_start) * 100)), 1)
    next_level_threshold = bt_thresholds[min(current_level_id, 3)][1] if current_level_id < 4 else None
    
    return jsonify({
        "username": current_user.username,
        "assessment_count": len(assessments),
        "evaluation_count": len(evaluations),
        "latest_level": latest_level,
        "current_level_id": current_level_id,
        "heatmap_weeks": weeks_data,
        "month_labels": month_labels,
        "weekday_labels": weekday_labels,
        "total_active_days": total_active,
        "max_count": max_count,
        "recent_7days_active": recent_count,
        "recent_7days_count": recent_total,
        "streak_days": streak,
        "learning_score": learning_score,
        "level_progress": level_progress,
        "next_level_threshold": next_level_threshold,
    })

# ================================================================
# 语音转文字 (iFlyTek) - 软隔离模式
# ================================================================
# 设计原则：语音输入只作为「快捷方式」而不是「必要入口」
# 当语音服务不可用时，自动降级为模拟模式，核心流程不受影响

@app.route('/api/stt', methods=['POST'])
@login_required
def api_stt():
    """接收前端音频文件，调用讯飞语音听写API转为文字
    软隔离设计：当STT服务不可用（未配置密钥、网络故障、超时）时，
    返回模拟文本，确保前端可继续使用文本输入完成全套流程"""
    if 'audio' not in request.files:
        return jsonify({'error': '未收到音频文件', 'mode': 'text_fallback'}), 400
    
    audio_file = request.files['audio']
    audio_data = audio_file.read()
    if len(audio_data) == 0:
        return jsonify({'error': '音频文件为空', 'mode': 'text_fallback'}), 400
    
    appid = os.environ.get('STT_APPID', '')
    api_key = os.environ.get('STT_API_KEY', '')
    api_secret = os.environ.get('STT_API_SECRET', '')
    
    # 软隔离：配置不全时返回模拟结果，不阻断流程
    if not appid or not api_key or not api_secret:
        app.logger.warning("STT配置未完成，使用模拟模式")
        return jsonify({
            'text': get_stt_mock_result(),
            'success': True,
            'mode': 'mock',
            'hint': '语音服务暂未配置，当前为模拟模式'
        })
    
    try:
        import websocket
        import time
        import ssl
        import threading
        from wsgiref.handlers import format_date_time
        from time import mktime
        
        # 从WAV文件中提取PCM数据（跳过44字节WAV头）
        pcm_data = audio_data[44:] if len(audio_data) > 44 else audio_data
        
        # 生成WebSocket URL
        now = datetime.now()
        date_str = format_date_time(mktime(now.timetuple()))
        
        host = "iat-api.xfyun.cn"
        signature_origin = f"host: {host}\ndate: {date_str}\nGET /v2/iat HTTP/1.1"
        
        signature_sha = hmac.new(api_secret.encode('utf-8'), signature_origin.encode('utf-8'),
                                digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(signature_sha).decode('utf-8')
        
        authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        
        url = f'wss://{host}/v2/iat?authorization={urllib.parse.quote(authorization)}&date={urllib.parse.quote(date_str)}&host={host}'
        
        # WebSocket回调
        result_text = []
        ws_error = None
        ws_closed = False
        timeout_event = threading.Event()
        
        def on_message(ws, message):
            nonlocal ws_closed
            try:
                data = json.loads(message)
                code = data.get('code', -1)
                if code == 0:
                    result_data = data.get('data', {}).get('result', {})
                    if 'ws' in result_data:
                        for ws_item in result_data['ws']:
                            for cw in ws_item.get('cw', []):
                                result_text.append(cw.get('w', ''))
                elif code != 0 and code != 1:
                    ws_error = f"讯飞API错误({code}): {data.get('message', '未知错误')}"
                    ws.close()
            except Exception as e:
                app.logger.error(f'WebSocket消息解析失败: {e}')
        
        def on_error(ws, error):
            nonlocal ws_error
            ws_error = f'WebSocket错误: {str(error)}'
        
        def on_close(ws, close_status_code, close_msg):
            nonlocal ws_closed
            ws_closed = True
        
        ws = websocket.WebSocketApp(url,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
        
        def on_open(ws):
            def run(*args):
                chunk_size = 1280
                status = 0
                total_chunks = len(pcm_data) // chunk_size + 1
                
                for i in range(0, len(pcm_data), chunk_size):
                    if timeout_event.is_set():
                        ws.close()
                        return
                    
                    chunk = pcm_data[i:i + chunk_size]
                    if i + chunk_size >= len(pcm_data):
                        status = 2
                    else:
                        status = 1 if i > 0 else 0
                    
                    send_data = {
                        'common': {'app_id': appid},
                        'business': {
                            'language': 'zh_cn',
                            'domain': 'iat',
                            'accent': 'mandarin',
                            'vad_eos': 3000,
                        },
                        'data': {
                            'status': status,
                            'format': 'audio/L16;rate=16000',
                            'encoding': 'raw',
                            'audio': base64.b64encode(chunk).decode('utf-8')
                        }
                    }
                    ws.send(json.dumps(send_data))
                    time.sleep(0.04)
                
                time.sleep(1)
                ws.close()
            
            import _thread as thread
            thread.start_new_thread(run, ())
        
        ws.on_open = on_open
        
        # 超时保护：15秒超时后自动降级
        def timeout_handler():
            time.sleep(15)
            if not ws_closed:
                timeout_event.set()
                ws.close()
        
        timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        timeout_thread.start()
        
        try:
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_interval=10, ping_timeout=5)
        except Exception as ws_e:
            app.logger.error(f'STT连接异常: {ws_e}')
        
        # 超时处理：返回模拟结果
        if timeout_event.is_set():
            app.logger.warning("STT调用超时，自动降级为模拟模式")
            return jsonify({
                'text': get_stt_mock_result(),
                'success': True,
                'mode': 'timeout_fallback',
                'hint': '语音识别超时，已切换至模拟模式'
            })
        
        # API错误处理：返回模拟结果
        if ws_error:
            app.logger.error(f'STT错误: {ws_error}')
            return jsonify({
                'text': get_stt_mock_result(),
                'success': True,
                'mode': 'error_fallback',
                'hint': '语音识别服务异常，已切换至模拟模式'
            })
        
        text = ''.join(result_text)
        
        # 识别结果为空时也返回模拟结果
        if not text:
            return jsonify({
                'text': get_stt_mock_result(),
                'success': True,
                'mode': 'empty_fallback',
                'hint': '语音无法识别，已切换至模拟模式'
            })
        
        return jsonify({'text': text, 'success': True, 'mode': 'real'})
            
    except ImportError as e:
        app.logger.error(f'STT依赖缺失: {e}')
        return jsonify({
            'text': get_stt_mock_result(),
            'success': True,
            'mode': 'dependency_fallback',
            'hint': '语音识别依赖缺失，已切换至模拟模式'
        })
    except Exception as e:
        app.logger.error(f'STT调用失败: {e}')
        return jsonify({
            'text': get_stt_mock_result(),
            'success': True,
            'mode': 'general_fallback',
            'hint': '语音识别异常，已切换至模拟模式'
        })


def get_stt_mock_result():
    """生成模拟语音识别结果，确保核心流程可继续运行"""
    mock_results = [
        "请帮我分析一下这个知识点",
        "我想了解更多关于机器学习的内容",
        "这道题怎么做",
        "讲解一下递归函数",
        "帮我生成一份学习计划",
        "这个概念不太理解",
        "请详细解释一下",
        "给我一些练习题",
        "我需要复习一下前面的内容",
        "这个算法的时间复杂度是多少"
    ]
    import random
    return random.choice(mock_results)


# ================================================================
# 新评估引擎 API
# ================================================================



@app.route('/api/behavior/log', methods=['POST'])
@login_required
def api_log_behavior():
    """记录学习行为"""
    data = request.get_json()
    if not data or 'behavior_type' not in data:
        return jsonify({'error': '缺少行为类型'}), 400
    
    behavior = BehaviorTracker.log(
        current_user.id,
        data.get('subject', 'computer_science'),
        data['behavior_type'],
        resource_type=data.get('resource_type'),
        resource_id=data.get('resource_id'),
        score=data.get('score'),
        time_spent=data.get('time_spent'),
        completion=data.get('completion'),
        detail=data.get('detail', {}),
    )
    
    return jsonify({'success': True, 'behavior_id': behavior.id})


@app.route('/api/behavior/stats', methods=['GET'])
@login_required
def api_behavior_stats():
    """获取行为统计数据"""
    subject = resolve_subject(request.args.get('subject', 'computer_science'))
    days = int(request.args.get('days', 30))
    
    behaviors = BehaviorTracker.get_user_behaviors(current_user.id, subject, days)
    stats = BehaviorTracker.analyze_behavior_stats(behaviors)
    
    return jsonify(stats)


@app.route('/api/plan/current', methods=['GET'])
@login_required
def api_current_plan():
    """获取当前学习计划"""
    subject = resolve_subject(request.args.get('subject', 'computer_science'))
    plan = LearningPlan.query.filter_by(
        user_id=current_user.id, subject=subject, is_active=True
    ).first()
    
    if not plan:
        return jsonify({'plan': None})
    
    return jsonify({
        'plan': {
            'id': plan.id,
            'subject': plan.subject,
            'current_level': plan.current_level,
            'target_level': plan.target_level,
            'adjustment_log': json.loads(plan.adjustment_log) if plan.adjustment_log else [],
            'resource_strategy': json.loads(plan.resource_strategy) if plan.resource_strategy else [],
            'started_at': plan.started_at.strftime('%Y-%m-%d'),
            'updated_at': plan.updated_at.strftime('%Y-%m-%d') if plan.updated_at else '',
        }
    })


# ===== 安全审核仪表盘 =====
@app.route('/admin/safety')
@login_required
def admin_safety_logs():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    logs = ContentSafetyLog.query.order_by(ContentSafetyLog.created_at.desc()).limit(50).all()
    total = ContentSafetyLog.query.count()
    blocked = ContentSafetyLog.query.filter_by(passed=False, check_result='flag').count()
    warn = ContentSafetyLog.query.filter_by(passed=False, check_result='warning').count()
    safe = ContentSafetyLog.query.filter_by(passed=True).count()
    return render_template('admin_safety_logs.html', logs=logs, stats={
        'total': total, 'blocked_count': blocked, 'warning_count': warn, 'pass_count': safe
    })


@app.route('/admin/safety/seed', methods=['POST'])
@login_required
def admin_safety_seed():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    from datetime import datetime, timedelta
    import json
    count = ContentSafetyLog.query.count()
    if count > 0:
        flash('已有审核记录，无需重复插入', 'info')
        return redirect(url_for('admin_safety_logs'))
    seeds = [
        ContentSafetyLog(
            user_id=current_user.id, content_type='user_submitted',
            content_preview='考试时如何作弊不被发现',
            check_result='flag', risk_type='sensitive', passed=False,
            risk_detail=json.dumps(['检测到「学术不端行为」类型敏感词：作弊']),
            created_at=datetime.utcnow() - timedelta(minutes=5),
        ),
        ContentSafetyLog(
            user_id=current_user.id, content_type='ai_response',
            content_preview='保证学会这个算法就能100%通过考试，肯定没问题',
            check_result='warning', risk_type='overpromise', passed=False,
            risk_detail=json.dumps(['检测到绝对化表述：保证学会', '检测到绝对化表述：100%', '检测到绝对化表述：肯定']),
            created_at=datetime.utcnow() - timedelta(minutes=3),
        ),
        ContentSafetyLog(
            user_id=current_user.id, content_type='ai_response',
            content_preview='引用一篇论文2021年的研究报告显示，这种方法效果显著',
            check_result='warning', risk_type='hallucination', passed=False,
            risk_detail=json.dumps(['模糊引用的学术来源：引用一篇论文2021...', '缺少作者信息，可能为AI生成的虚假引用']),
            created_at=datetime.utcnow() - timedelta(minutes=1),
        ),
    ]
    for s in seeds:
        db.session.add(s)
    db.session.commit()
    flash('已插入3条示例拦截记录', 'success')
    return redirect(url_for('admin_safety_logs'))


@app.route('/admin/safety/clear')
@login_required
def admin_safety_clear():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    ContentSafetyLog.query.delete()
    db.session.commit()
    flash('审核日志已清空', 'success')
    return redirect(url_for('admin_safety_logs'))


@app.route('/api/safety/check', methods=['POST'])
@login_required
def api_safety_check():
    """内容安全检查"""
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': '缺少内容'}), 400
    
    subject = resolve_subject(data.get('subject', 'computer_science'))
    content = data['content']
    
    check_result = SafetyFilter.comprehensive_check(content, subject)
    
    # 记录审核日志
    log = ContentSafetyLog(
        user_id=current_user.id,
        content_type=data.get('content_type', 'user_submitted'),
        content_preview=content[:200],
        check_result='pass' if check_result['passed'] else 'flag',
        risk_detail=json.dumps(check_result['issues'], ensure_ascii=False),
        passed=check_result['passed'],
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify(check_result)

def find_available_port(start_port=5000):
    import socket
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port

if __name__ == '__main__':
    desired_port = int(os.environ.get('PORT', 5000))
    actual_port = find_available_port(desired_port)
    if actual_port != desired_port:
        print(f"Port {desired_port} is in use, using port {actual_port} instead...")
    app.run(host='0.0.0.0', port=actual_port, debug=True)
