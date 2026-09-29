"""管理后台蓝图"""
import json, logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user, login_user
from sqlalchemy import func as sa_func

from models import db, User, Assessment, EvaluationReport, LearningBehavior, TutorSession

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin_bp', __name__)


@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """管理员登录"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username, is_admin=True).first()
        if user and user.check_password(password):
            login_user(user)
            flash('管理员登录成功', 'success')
            return redirect(url_for('admin_bp.admin_panel'))
        else:
            flash('管理员账号或密码错误', 'error')
    
    return render_template('admin_login.html')


@admin_bp.route('/admin')
@login_required
def admin_panel():
    """管理后台主页"""
    if not current_user.is_admin:
        flash('无权访问管理后台', 'error')
        return redirect(url_for('dashboard'))
    
    from models import LearningPath, GeneratedResource, ContentSafetyLog
    
    today = datetime.now().date()
    new_users_today = User.query.filter(
        sa_func.date(User.created_at) == today
    ).count()
    
    total_users = User.query.count()
    total_assessments = Assessment.query.count()
    total_evaluations = EvaluationReport.query.count()
    total_behaviors = LearningBehavior.query.count()
    total_tutors = TutorSession.query.count()
    total_paths = LearningPath.query.count()
    total_resources = GeneratedResource.query.count()
    total_safety_logs = ContentSafetyLog.query.count()
    
    subject_dist = db.session.query(
        Assessment.subject, sa_func.count(Assessment.id)
    ).group_by(Assessment.subject).all()
    
    behavior_type_dist = db.session.query(
        LearningBehavior.behavior_type, sa_func.count(LearningBehavior.id)
    ).group_by(LearningBehavior.behavior_type).all()
    
    eval_scores = [r.overall_score for r in EvaluationReport.query.all() if r.overall_score]
    avg_score = round(sum(eval_scores) / len(eval_scores), 1) if eval_scores else None
    
    max_subject_count = max([c for _, c in subject_dist], default=1)
    subject_distribution = [
        {'subject': s, 'count': c, 'pct': round(c / max_subject_count * 100, 0)}
        for s, c in subject_dist
    ]
    
    max_behavior_count = max([c for _, c in behavior_type_dist], default=1)
    behavior_distribution = [
        {'type': t, 'count': c, 'pct': round(c / max_behavior_count * 100, 0)}
        for t, c in behavior_type_dist
    ]
    
    stats = {
        'user_count': total_users,
        'new_users_today': new_users_today,
        'assessment_count': total_assessments,
        'assessment_subjects': len(subject_dist),
        'evaluation_count': total_evaluations,
        'avg_score': avg_score,
        'behavior_count': total_behaviors,
        'behavior_types': len(behavior_type_dist),
        'subject_distribution': subject_distribution,
        'behavior_distribution': behavior_distribution,
        'tutor_count': total_tutors,
        'path_count': total_paths,
        'resource_count': total_resources,
        'safety_log_count': total_safety_logs,
    }
    
    users = User.query.order_by(User.created_at.desc()).limit(20).all()
    
    recent_behaviors = LearningBehavior.query.order_by(
        LearningBehavior.created_at.desc()
    ).limit(10).all()
    
    return render_template('admin.html',
        stats=stats,
        users=users,
        recent_behaviors=recent_behaviors,
        now=datetime.now().strftime('%Y-%m-%d %H:%M')
    )
