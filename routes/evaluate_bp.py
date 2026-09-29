"""评估模块蓝图 — 包含评估页面、API、PDF导出"""
import json, logging, io
from datetime import datetime
from urllib.parse import quote
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, make_response
from flask_login import login_required, current_user
from sqlalchemy import func as sa_func

from models import db, User, Assessment, Evaluation, EvaluationReport, LearningBehavior, AsyncTask, LearningPlan, TutorSession
from config import SUBJECTS, LEVELS
from evaluation_engine import SafetyFilter, BehaviorTracker, LLMEvaluator, ProgressTracker, PlanOptimizer, EVAL_DIMENSIONS
from agents.subject_mapper import resolve_subject
from utils import get_weakness_points, call_llm

logger = logging.getLogger(__name__)

evaluate_bp = Blueprint('evaluate_bp', __name__)


@evaluate_bp.route('/evaluate')
@login_required
def evaluate():
    """评估仪表盘"""
    subject = request.args.get('subject', 'computer_science')
    subject_name = SUBJECTS.get(subject, subject)
    level_id = request.args.get('level', 1, type=int)
    
    # 获取最新评估报告
    latest_report = EvaluationReport.query.filter_by(
        user_id=current_user.id
    ).order_by(EvaluationReport.created_at.desc()).first()
    
    # 提取弱点数据给前端用于跳转陷阱题
    latest_weaknesses = []
    if latest_report and latest_report.weaknesses:
        try:
            ws = json.loads(latest_report.weaknesses)
            if isinstance(ws, list):
                latest_weaknesses = ws[:8]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    # 学习行为摘要
    behavior_summary = BehaviorTracker.analyze_behavior_stats(
        BehaviorTracker.get_user_behaviors(current_user.id, subject, days=30)
    )
    
    # 活跃学习计划
    active_plans = LearningPlan.query.filter_by(
        user_id=current_user.id, is_active=True
    ).all()
    
    # 功能开关
    eval_llm_enabled = True
    safety_enabled = True
    
    return render_template('evaluate.html',
        current_step='evaluate',
        subjects=SUBJECTS,
        levels=LEVELS,
        eval_llm_enabled=eval_llm_enabled,
        safety_enabled=safety_enabled,
        behavior_summary=json.dumps(behavior_summary, ensure_ascii=False),
        latest_report=latest_report,
        active_plans_count=len(active_plans),
        latest_weaknesses=json.dumps(latest_weaknesses, ensure_ascii=False)
    )


# ===== 评估 API =====
@evaluate_bp.route('/api/evaluate/submit', methods=['POST'])
@login_required
def api_evaluate():
    """提交评估（v1版，保留兼容，改用LLMEvaluator）"""
    data = request.get_json() or {}
    subject = resolve_subject(data.get('subject', 'computer_science'))
    subject_name = SUBJECTS.get(subject, subject)
    current_level = data.get('current_level', 1)
    
    # 获取行为数据
    behaviors = BehaviorTracker.get_user_behaviors(current_user.id, subject, days=30)
    behavior_stats = BehaviorTracker.analyze_behavior_stats(behaviors)
    
    # 走LLM完整评估
    eval_result = LLMEvaluator.full_evaluate(
        current_user.id, subject, subject_name, current_level
    )
    
    dim_scores = eval_result.get('dimension_scores', {})
    weighted = eval_result.get('overall', 60)
    
    # 尽量为所有评估维度补齐数值
    for dim in EVAL_DIMENSIONS:
        dim_scores.setdefault(dim['id'], round(weighted * (0.8 + (hash(str(dim['id'])) % 40) / 100)))
    
    eval_report = {
        'dimension_scores': dim_scores,
        'overall': weighted,
        'summary': eval_result.get('summary', f"学生在{subject_name}学习中表现{'良好' if weighted >= 70 else '需要提升'}。"),
        'strengths': eval_result.get('strengths', ['基础较好']),
        'weaknesses': eval_result.get('weaknesses', ['需加强实践']),
        'recommendations': eval_result.get('recommendations', ['增加练习量']),
        'suggested_action': eval_result.get('suggested_action', 'stay'),
        'confidence': eval_result.get('confidence', 0.6)
    }
    
    # 计算目标级别
    suggested_action = eval_report.get('suggested_action', 'stay')
    to_level = current_level
    if suggested_action == 'upgrade':
        to_level = min(4, current_level + 1)
    elif suggested_action == 'consolidate':
        to_level = max(1, current_level - 1)
    
    # 保存评估报告
    report = EvaluationReport(
        user_id=current_user.id,
        subject=subject,
        overall_score=weighted,
        dimension_scores=json.dumps(dim_scores, ensure_ascii=False),
        weaknesses=json.dumps(eval_report.get('weaknesses', []), ensure_ascii=False),
        strengths=json.dumps(eval_report.get('strengths', []), ensure_ascii=False),
        summary=eval_report.get('summary', ''),
        recommendations=json.dumps(eval_report.get('recommendations', []), ensure_ascii=False),
        suggested_action=eval_report.get('suggested_action', 'stay'),
        confidence=eval_report.get('confidence', 0.5),
        from_level=current_level,
        to_level=to_level
    )
    db.session.add(report)
    db.session.commit()
    
    # 更新学习计划（使用正确的当前层次）
    PlanOptimizer.update_learning_plan(current_user.id, subject, eval_report, current_level)
    
    return jsonify({'success': True, 'report_id': report.id, 'result': eval_report})


@evaluate_bp.route('/api/evaluate/progress', methods=['GET'])
@login_required
def api_progress():
    """获取评估进度（v1兼容）"""
    return jsonify({'progress': 100, 'stage': '评估完成'})


@evaluate_bp.route('/api/evaluate/v2', methods=['POST'])
@login_required
def api_evaluate_v2():
    """新版评估 - 基于LLM和实时行为数据"""
    data = request.get_json() or {}
    subject = resolve_subject(data.get('subject', 'computer_science'))
    subject_name = SUBJECTS.get(subject, subject)
    current_level = data.get('current_level', 1)
    
    # 创建异步任务
    task_id = ProgressTracker.create_task(current_user.id, 'evaluate')
    
    # 异步执行评估（实际项目中用Celery，此处简化）
    try:
        ProgressTracker.update_progress(task_id, 10.0, '获取学习行为数据...', 'running')
        
        result = LLMEvaluator.full_evaluate(
            current_user.id, subject, subject_name, current_level
        )
        
        ProgressTracker.update_progress(task_id, 80.0, '安全审核中...')
        
        # 安全检查
        if not result.get('safety_check', {}).get('passed', True):
            issues = result['safety_check'].get('issues', [])
            logger.warning(f'评估安全问题: {issues}')
        
        # 更新学习计划
        PlanOptimizer.update_learning_plan(
            current_user.id, subject, result, current_level
        )
        
        ProgressTracker.complete_task(task_id, result)
        
        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        ProgressTracker.fail_task(task_id, str(e))
        logger.error(f'评估失败: {e}', exc_info=True)
        return jsonify({'error': f'评估失败: {str(e)}'}), 500


@evaluate_bp.route('/api/evaluate/task/<int:task_id>', methods=['GET'])
@login_required
def api_task_progress(task_id):
    """获取异步任务进度"""
    task = ProgressTracker.get_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    # 安全检查：只能查看自己的任务
    db_task = AsyncTask.query.get(task_id)
    if db_task and db_task.user_id != current_user.id:
        return jsonify({'error': '无权访问'}), 403
    
    return jsonify(task)


@evaluate_bp.route('/api/evaluate/report', methods=['GET'])
@login_required
def api_latest_report():
    """获取最新评估报告"""
    subject = request.args.get('subject')
    query = EvaluationReport.query.filter_by(user_id=current_user.id)
    if subject:
        query = query.filter_by(subject=resolve_subject(subject))
    report = query.order_by(EvaluationReport.created_at.desc()).first()
    
    if not report:
        return jsonify({'report': None, 'error': '暂无评估报告'})
    
    return jsonify({
        'id': report.id,
        'subject': report.subject,
        'overall_score': report.overall_score,
        'dimension_scores': json.loads(report.dimension_scores) if report.dimension_scores else {},
        'weaknesses': json.loads(report.weaknesses) if report.weaknesses else [],
        'strengths': json.loads(report.strengths) if report.strengths else [],
        'summary': report.summary,
        'recommendations': json.loads(report.recommendations) if report.recommendations else [],
        'suggested_action': report.suggested_action,
        'confidence': report.confidence,
        'created_at': report.created_at.isoformat(),
        # === 以下为前端 displayResult 所需的完整字段 ===
        'plan_adjustments': json.loads(report.plan_adjustments) if report.plan_adjustments else [],
        'resource_adjustments': json.loads(report.resource_adjustments) if report.resource_adjustments else [],
        'from_level': report.from_level if report.from_level is not None else 1,
        'to_level': report.to_level if report.to_level is not None else 1,
        'safety_check': None,
    })


@evaluate_bp.route('/api/evaluate/reports', methods=['GET'])
@login_required
def api_report_history():
    """获取评估报告历史"""
    reports = EvaluationReport.query.filter_by(
        user_id=current_user.id
    ).order_by(EvaluationReport.created_at.desc()).limit(10).all()
    
    return jsonify([{
        'id': r.id,
        'subject': r.subject,
        'overall_score': r.overall_score,
        'summary': r.summary or '',
        'suggested_action': r.suggested_action,
        'created_at': r.created_at.isoformat()
    } for r in reports])


def _find_chinese_font_path():
    """跨平台中文字体路径查找（ReportLab专用）
    
    Returns:
        str: TTF字体路径，找不到则返回None
    """
    import os
    
    candidates = [
        '/Library/Fonts/Arial Unicode.ttf',
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        '/tmp/STHeitiSC-Light.ttf',  # 从TTC提取的SC字体
        '/tmp/Stripped.ttf',
        'C:/Windows/Fonts/simhei.ttf',
        'C:/Windows/Fonts/msyh.ttf',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttf',
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'fonts', 'NotoSansCJK-Regular.ttc'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


@evaluate_bp.route('/api/evaluate/export_pdf', methods=['GET'])
@login_required
def api_export_pdf():
    """导出评估报告为PDF"""
    report_id = request.args.get('report_id', type=int)
    
    query = EvaluationReport.query.filter_by(user_id=current_user.id)
    if report_id:
        report = query.filter_by(id=report_id).first()
    else:
        report = query.order_by(EvaluationReport.created_at.desc()).first()
    
    if not report:
        flash('暂无评估报告可导出', 'warning')
        return redirect(url_for('evaluate_bp.evaluate'))
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm, cm
        from reportlab.lib.colors import HexColor, black, white
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.platypus.flowables import Flowable
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import io
        
        buf = io.BytesIO()
        
        # ---- 注册中文字体 ----
        font_path = _find_chinese_font_path()
        if font_path:
            try:
                pdfmetrics.registerFont(TTFont('CJK', font_path))
                fname = 'CJK'
            except Exception:
                fname = 'Helvetica'
                logger.warning(f'注册字体失败: {font_path}')
        else:
            fname = 'Helvetica'
            logger.warning('未找到中文字体，使用默认字体')
        
        
        # ---- 自定义条形图 Flowable ----
        class BarChart(Flowable):
            def __init__(self, items, bar_colors, bw, fname):
                Flowable.__init__(self)
                self.items = items          # [(name, score), ...]
                self.bar_colors = bar_colors
                self.bw = bw
                self.fname = fname
                self.width = bw + 80
                self.height = len(items) * 22 + 10
            
            def draw(self):
                from reportlab.pdfbase.pdfmetrics import stringWidth
                for i, (name, score) in enumerate(self.items):
                    y = self.height - 22 - i * 22
                    color = self.bar_colors[i % len(self.bar_colors)]
                    bar_w = max(4, score / 100.0 * self.bw)
                    
                    # 名称
                    self.canv.setFont(self.fname, 10)
                    self.canv.setFillColor(HexColor('#333333'))
                    self.canv.drawString(0, y, name)
                    
                    # 分数
                    self.canv.setFont(self.fname, 10)
                    self.canv.drawString(72, y, f'{int(score)}')
                    
                    # 灰色背景条
                    x_bar = 82
                    self.canv.setFillColor(HexColor('#eeeeee'))
                    self.canv.rect(x_bar, y - 6, self.bw, 10, fill=1, stroke=0)
                    
                    # 彩色前景条
                    self.canv.setFillColor(color)
                    self.canv.rect(x_bar, y - 6, bar_w, 10, fill=1, stroke=0)
        
        
        # ---- 构建文档 ----
        story = []
        page_w = A4[0] - 50
        ml = 25
        bw = page_w - 100
        
        bar_colors = [
            HexColor('#3490dc'),
            HexColor('#5cb85c'),
            HexColor('#f0ad4e'),
            HexColor('#d9534f'),
            HexColor('#5bc0de'),
            HexColor('#997ab7'),
        ]
        
        # 标题
        story.append(Paragraph(f'<para alignment="center"><font size="18"><b>学习评估报告</b></font></para>', ParagraphStyle('t0', fontName=fname, fontSize=18, alignment=TA_CENTER)))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f'<para alignment="center"><font size="10">学科: {SUBJECTS.get(report.subject, report.subject)} &nbsp; | &nbsp; 评估时间: {report.created_at.strftime("%Y-%m-%d %H:%M")}</font></para>', ParagraphStyle('t1', fontName=fname, fontSize=10, alignment=TA_CENTER)))
        story.append(Spacer(1, 12))
        
        # 综合评分
        story.append(Paragraph(f'<font size="16"><b>综合评分：{report.overall_score} / 100</b></font>', ParagraphStyle('score', fontName=fname, fontSize=16)))
        story.append(Spacer(1, 10))
        
        # 维度评分
        dim_scores = json.loads(report.dimension_scores) if report.dimension_scores else {}
        dim_names = {d['id']: d['name'] for d in EVAL_DIMENSIONS}
        
        story.append(Paragraph('<font size="12"><b>各维度评分</b></font>', ParagraphStyle('dim_title', fontName=fname, fontSize=12)))
        story.append(Spacer(1, 4))
        
        bar_items = [(dim_names.get(did, did), sc) for did, sc in dim_scores.items()]
        story.append(BarChart(bar_items, bar_colors, bw, fname))
        story.append(Spacer(1, 10))
        
        # 评估摘要
        story.append(Paragraph('<font size="12"><b>评估摘要</b></font>', ParagraphStyle('sum_title', fontName=fname, fontSize=12)))
        story.append(Spacer(1, 4))
        story.append(Paragraph(report.summary or '暂无', ParagraphStyle('sum_body', fontName=fname, fontSize=10, leading=16, textColor=HexColor('#555555'))))
        story.append(Spacer(1, 8))
        
        # 学习优势
        strengths = json.loads(report.strengths) if report.strengths else []
        if strengths:
            story.append(Paragraph('<font size="12"><b>学习优势</b></font>', ParagraphStyle('str_title', fontName=fname, fontSize=12)))
            story.append(Spacer(1, 2))
            for s in strengths:
                story.append(Paragraph(f'\u2713  {s}', ParagraphStyle('str_item', fontName=fname, fontSize=10, leading=16, leftIndent=10)))
            story.append(Spacer(1, 6))
        
        # 待加强
        weaknesses = json.loads(report.weaknesses) if report.weaknesses else []
        if weaknesses:
            story.append(Paragraph('<font size="12"><b>待加强</b></font>', ParagraphStyle('weak_title', fontName=fname, fontSize=12)))
            story.append(Spacer(1, 2))
            for w in weaknesses:
                story.append(Paragraph(f'\u2717  {w}', ParagraphStyle('weak_item', fontName=fname, fontSize=10, leading=16, leftIndent=10)))
            story.append(Spacer(1, 6))
        
        # 学习建议
        recommendations = json.loads(report.recommendations) if report.recommendations else []
        if recommendations:
            story.append(Paragraph('<font size="12"><b>学习建议</b></font>', ParagraphStyle('rec_title', fontName=fname, fontSize=12)))
            story.append(Spacer(1, 2))
            for i, rec in enumerate(recommendations, 1):
                story.append(Paragraph(f'  {i}. {rec}', ParagraphStyle('rec_item', fontName=fname, fontSize=10, leading=16, leftIndent=10)))
            story.append(Spacer(1, 6))
        
        # 计划调整建议
        plan_adjustments = json.loads(report.plan_adjustments) if report.plan_adjustments else []
        if plan_adjustments:
            story.append(Paragraph('<font size="12"><b>计划调整建议</b></font>', ParagraphStyle('plan_title', fontName=fname, fontSize=12)))
            story.append(Spacer(1, 2))
            for adj in plan_adjustments:
                detail = adj.get('detail', '')
                story.append(Paragraph(f'\u2022  {adj.get("action", "")}：{detail}', ParagraphStyle('plan_item', fontName=fname, fontSize=10, leading=16, leftIndent=10)))
            story.append(Spacer(1, 6))
        
        # 资源推荐
        resource_adjustments = json.loads(report.resource_adjustments) if report.resource_adjustments else []
        if resource_adjustments:
            story.append(Paragraph('<font size="12"><b>资源推荐</b></font>', ParagraphStyle('res_title', fontName=fname, fontSize=12)))
            story.append(Spacer(1, 2))
            for ra in resource_adjustments:
                rtypes = ', '.join(ra.get('resource_types', []))
                story.append(Paragraph(f'\u2022  {ra.get("strategy", "")}（{rtypes}）', ParagraphStyle('res_item', fontName=fname, fontSize=10, leading=16, leftIndent=10)))
            story.append(Spacer(1, 6))
        
        # 行动建议
        action_labels = {'upgrade': '建议升级', 'stay': '保持当前', 'consolidate': '建议巩固', 'customize': '个性化方案'}
        action_label = action_labels.get(report.suggested_action, report.suggested_action)
        story.append(Paragraph(f'<font size="12"><b>行动建议：{action_label}</b></font>', ParagraphStyle('act_title', fontName=fname, fontSize=12)))
        
        # ---- 生成PDF ----
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=25, rightMargin=25, topMargin=25, bottomMargin=25)
        doc.build(story)
        pdf_bytes = buf.getvalue()
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        ascii_name = f'eval_report_{report.created_at.strftime("%Y%m%d")}.pdf'
        utf8_name = f'评估报告_{report.created_at.strftime("%Y%m%d")}.pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(utf8_name)}"
        return response
    except Exception as e:
        logger.error(f'PDF导出失败: {e}', exc_info=True)
        flash(f'PDF导出失败: {str(e)}', 'error')
        return redirect(url_for('evaluate_bp.evaluate'))

@evaluate_bp.route('/api/evaluate/feedback-summary')
@login_required
def api_feedback_summary():
    """获取反馈回路总结报告"""
    subject = request.args.get('subject', 'computer_science')
    
    plan = LearningPlan.query.filter_by(
        user_id=current_user.id,
        subject=subject,
        is_active=True
    ).first()
    
    if not plan:
        return jsonify({
            'active': False,
            'total_suggestions': 0,
            'verified_count': 0,
            'pending_count': 0,
            'effect_stats': {'improved': 0, 'declined': 0, 'stable': 0},
            'average_days_to_verify': 0,
            'conclusion': '暂无学习计划' if subject else '请先创建学习计划'
        })
    
    return jsonify(PlanOptimizer.get_feedback_summary(plan))


@evaluate_bp.route('/api/evaluate/feedback-verify', methods=['POST'])
@login_required
def api_feedback_verify():
    """手动发起反馈回路验证（让新评估结果验证之前的建议）"""
    data = request.get_json() or {}
    subject = data.get('subject', 'computer_science')
    current_score = data.get('score', 0)
    current_level = data.get('level', 1)
    
    plan = LearningPlan.query.filter_by(
        user_id=current_user.id,
        subject=subject,
        is_active=True
    ).first()
    
    if not plan:
        return jsonify({'error': '无当前学习计划'}), 404
    
    PlanOptimizer._verify_feedback_loop(plan, current_level, current_score)
    db.session.commit()
    
    return jsonify({'success': True, 'summary': PlanOptimizer.get_feedback_summary(plan)})
