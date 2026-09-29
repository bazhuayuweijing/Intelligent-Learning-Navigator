"""辅导员模块蓝图 — 辅导页面 + 对话API"""
import json, logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from models import db, TutorSession, EvaluationReport, LearningBehavior
from config import SUBJECTS
from evaluation_engine import BehaviorTracker, SafetyFilter
from llm_client import spark_chat, load_spark_config
from agents.subject_mapper import resolve_subject
from utils import get_weakness_points

logger = logging.getLogger(__name__)

tutor_bp = Blueprint('tutor_bp', __name__)


@tutor_bp.route('/tutor')
@login_required
def tutor():
    """AI辅导员页面"""
    subject = request.args.get('subject', 'computer_science')
    subject_name = SUBJECTS.get(subject, subject)
    
    # 获取最新评估数据用于上下文
    latest_eval = EvaluationReport.query.filter_by(
        user_id=current_user.id
    ).order_by(EvaluationReport.created_at.desc()).first()
    
    eval_context = {}
    if latest_eval:
        eval_context['eval_overall'] = latest_eval.overall_score
        if latest_eval.weaknesses:
            try:
                ws = json.loads(latest_eval.weaknesses)
                if isinstance(ws, list) and ws:
                    eval_context['eval_weaknesses'] = ws[:5]
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        subject_eval = EvaluationReport.query.filter_by(
            user_id=current_user.id, subject=subject
        ).order_by(EvaluationReport.created_at.desc()).first()
        if subject_eval:
            eval_context['eval_subject_score'] = subject_eval.overall_score
            eval_context['eval_subject_weaknesses'] = json.loads(subject_eval.weaknesses)[:5] \
                if subject_eval.weaknesses else []
    
    return render_template('tutor.html',
        current_step='tutor',
        subjects=SUBJECTS,
        levels=[1,2,3,4],
        subject_name=subject_name,
        subject_code=subject,
        eval_context=json.dumps(eval_context, ensure_ascii=False)
    )


@tutor_bp.route('/api/tutor/ask', methods=['POST'])
@login_required
def api_tutor_ask():
    """AI辅导员对话接口"""
    data = request.get_json() or {}
    question = data.get('question', '')
    subject = resolve_subject(data.get('subject', 'computer_science'))
    subject_name = SUBJECTS.get(subject, subject)
    history = data.get('history', [])
    
    if not question:
        return jsonify({'error': '请输入问题'}), 400
    
    # === 实时安全审核：学生输入拦截 ===
    safety = SafetyFilter.comprehensive_check(question, subject=subject)
    if not safety['passed'] and safety['risk_level'] == 'reject':
        # 记录拦截日志
        try:
            from models import ContentSafetyLog
            log = ContentSafetyLog(
                user_id=current_user.id,
                content_type='tutor_input',
                content_preview=question[:200],
                issues=json.dumps(safety['issues'], ensure_ascii=False),
                risk_level='reject',
                action_taken='blocked',
                checked_by=' SafetyFilter.realtime'
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.error(f"安全日志记录失败: {e}")
        return jsonify({
            'error': '输入内容包含敏感或违规信息，已被拦截。如有疑问请联系管理员。',
            'blocked': True,
            'risk_level': 'reject'
        }), 403
    
    # 查找或创建辅导会话
    session_obj = TutorSession.query.filter_by(
        user_id=current_user.id, subject=subject, is_active=True
    ).first()
    
    if not session_obj:
        session_obj = TutorSession(
            user_id=current_user.id,
            subject=subject,
            level_id=1,
            is_active=True
        )
        db.session.add(session_obj)
        db.session.commit()
    
    # 构建评估上下文
    eval_context = {}
    latest_eval = EvaluationReport.query.filter_by(
        user_id=current_user.id
    ).order_by(EvaluationReport.created_at.desc()).first()
    
    if latest_eval:
        eval_context['eval_overall'] = latest_eval.overall_score
        if latest_eval.weaknesses:
            try:
                ws = json.loads(latest_eval.weaknesses)
                if isinstance(ws, list) and ws:
                    eval_context['eval_weaknesses'] = ws[:5]
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        subject_eval = EvaluationReport.query.filter_by(
            user_id=current_user.id, subject=subject
        ).order_by(EvaluationReport.created_at.desc()).first()
        if subject_eval:
            eval_context['eval_subject_score'] = subject_eval.overall_score
            eval_context['eval_subject_weaknesses'] = json.loads(subject_eval.weaknesses)[:5] \
                if subject_eval.weaknesses else []
    
    # 调用LLM
    try:
        from llm_client import load_spark_config
        cfg = load_spark_config()
    except Exception:
        cfg = {}
    
    # === 苏格拉底式对话模式（至少5轮引导） ===
    # 从前端获取当前轮数，如果没有则计算
    socratic_round = data.get('socratic_round', 0)
    if not socratic_round and history:
        socratic_round = len([h for h in history if h.get('role') == 'user'])
    
    # 前10轮启用苏格拉底模式
    socratic_mode = socratic_round < 10
    
    if socratic_mode:
        system_prompt = (
            f"你是一位擅长苏格拉底式教学的AI辅导员，正在辅导学生学习「{subject_name}」。\n"
            f"学生姓名：{current_user.username}\n"
            f"\n【苏格拉底式教学原则】\n"
            f"1. 不直接给答案，而是通过提问引导学生自己发现答案\n"
            f"2. 使用追问技巧：'你为什么这么认为？'、'这个结论的前提是什么？'、'有没有反例？'\n"
            f"3. 将大问题拆解为小问题，逐步引导学生思考\n"
            f"4. 鼓励学生质疑和反思，培养批判性思维\n"
            f"5. 每轮对话至少包含1-2个引导性问题\n"
            f"6. 如果学生连续3轮仍无法得出答案，再给出部分提示\n"
            f"\n【对话结构要求】\n"
            f"- 先肯定学生的思考方向（如有）\n"
            f"- 提出引导性问题，帮助学生深入思考\n"
            f"- 必要时给出思考框架或类比，但不直接给结论\n"
            f"- 以开放性问题结束，鼓励学生继续探索\n"
        )
    else:
        system_prompt = (
            f"你是一位AI学习辅导员，正在辅导学生学习「{subject_name}」。\n"
            f"学生姓名：{current_user.username}\n"
            f"请根据学生的学科特点和问题，提供有针对性的辅导回答。\n"
            f"回答要求：\n"
            f"1. 耐心细致，鼓励式引导\n"
            f"2. 结合学科特性给出具体建议\n"
            f"3. 适当提问引导学生深入思考\n"
            f"4. 如果合适，可以推荐相关学习资源\n"
        )
    
    if eval_context:
        system_prompt += (
            f"\n学生评估数据参考：\n"
            f"- 综合评分：{eval_context.get('eval_overall', '暂无')}\n"
        )
        if eval_context.get('eval_subject_weaknesses'):
            ws = eval_context['eval_subject_weaknesses']
            system_prompt += f"- {subject_name}薄弱环节：{'、'.join(ws[:3])}\n"
    
    # 构造对话历史（苏格拉底模式保留更多历史）
    history_limit = 12 if socratic_mode else 6
    messages = []
    for h in history[-history_limit:]:
        if isinstance(h, dict):
            messages.append(f"{'用户' if h.get('role') == 'user' else '辅导员'}: {h.get('content', '')}")
    
    user_content = (
        f"历史对话（第{socratic_round + 1}轮）：\n" + "\n".join(messages[-history_limit:]) + "\n\n"
        f"学生最新提问：{question}\n"
    )
    
    if socratic_mode:
        user_content += (
            f"\n【当前教学模式】苏格拉底式引导（第{socratic_round + 1}/10轮）\n"
            f"请通过提问引导学生自己发现答案，不要直接给出完整解答。"
        )
    
    answer = spark_chat(system_prompt, user_content, temperature=0.7 if socratic_mode else 0.8, max_tokens=1024)
    
    # === 实时安全审核：AI输出防幻觉 ===
    if answer:
        output_safety = SafetyFilter.comprehensive_check(answer, subject=subject)
        if output_safety['risk_level'] in ('flag', 'reject'):
            # 高风险输出：净化后返回，并记录
            answer, _ = SafetyFilter.sanitize_output(answer, subject=subject)
            try:
                from models import ContentSafetyLog
                log = ContentSafetyLog(
                    user_id=current_user.id,
                    content_type='tutor_output',
                    content_preview=answer[:200],
                    issues=json.dumps(output_safety['issues'], ensure_ascii=False),
                    risk_level=output_safety['risk_level'],
                    action_taken='sanitized',
                    checked_by='SafetyFilter.realtime'
                )
                db.session.add(log)
                db.session.commit()
            except Exception as e:
                logger.error(f"安全日志记录失败: {e}")
        elif output_safety['risk_level'] == 'warning':
            # 低风险：记录但不拦截
            try:
                from models import ContentSafetyLog
                log = ContentSafetyLog(
                    user_id=current_user.id,
                    content_type='tutor_output',
                    content_preview=answer[:200],
                    issues=json.dumps(output_safety['issues'], ensure_ascii=False),
                    risk_level='warning',
                    action_taken='logged',
                    checked_by='SafetyFilter.realtime'
                )
                db.session.add(log)
                db.session.commit()
            except Exception as e:
                logger.error(f"安全日志记录失败: {e}")
    
    if not answer:
        # 降级：基于问题关键词做差异化回答
        q = question.lower()
        if any(w in q for w in ['什么是', '概念', '定义', '解释']):
            answer = f"关于「{question[:60]}」这个概念，它属于{subject_name}的基础知识点。理解它的关键是把握核心定义和与相关概念的区别。建议你先梳理课本上的定义，然后找一个具体的例子对照理解。你目前的理解卡在哪里？"
        elif any(w in q for w in ['怎么', '如何', '方法', '步骤']):
            answer = f"关于「{question[:60]}」这个操作类问题，建议你按以下步骤来：第一，确认前置知识已经掌握；第二，按照规范的流程操作一遍；第三，记录遇到的问题。你能先说说你做到哪一步了吗？"
        elif any(w in q for w in ['区别', '对比', 'vs', '不同']):
            answer = f"要对比「{question[:60]}」之间的区别，可以先从各自的核心定义出发，再分析它们的应用场景和优缺点。建议你画一个对比表格来理清思路。你更关注哪方面的差异？"
        elif any(w in q for w in ['代码', '编程', '实现', '报错', 'error']):
            answer = f"关于「{question[:60]}」的编程实现问题，建议你先自己尝试写一遍核心逻辑，遇到具体的报错信息可以贴给我分析。编码中的错误通常来自边界条件或逻辑漏洞——你碰到的是什么类型的报错？"
        else:
            answer = f"关于你提出的「{question[:60]}」，在{subject_name}的学习中需要先从基础知识入手。你能先说说你已经了解了哪些相关内容吗？这样我可以更有针对性地帮你。"
    
    db.session.commit()
    
    # 保存问答内容到辅导会话记录
    try:
        session_obj.question = question[:2000]
        session_obj.answer = answer[:4000] if answer else None
        db.session.commit()
    except Exception as e:
        logger.error(f"保存辅导问答记录失败: {e}")
    
    # 记录学习行为
    try:
        BehaviorTracker.log(
            user_id=current_user.id,
            subject=subject,
            behavior_type='tutor_ask',
            resource_type='tutor',
            time_spent=30,
            detail={'question_length': len(question), 'question': question[:100]}
        )
    except Exception as e:
        logger.error(f"记录学习行为失败: {e}")
    
    # 提取并记录知识点
    try:
        from utils import extract_knowledge_points, add_or_update_knowledge_point
        tutor_text = f"{question} {answer}"
        knowledge_points = extract_knowledge_points(tutor_text, subject)
        for kp in knowledge_points:
            add_or_update_knowledge_point(current_user.id, subject, kp[0])
    except Exception as e:
        logger.error(f"记录知识点失败: {e}")
    
    return jsonify({
        'answer': answer,
        'socratic_round': socratic_round + 1,
        'socratic_mode': socratic_mode,
        '_eval_context': eval_context
    })


@tutor_bp.route('/api/tutor/history', methods=['GET'])
@login_required
def api_tutor_history():
    """获取辅导历史"""
    subject = request.args.get('subject')
    query = TutorSession.query.filter_by(user_id=current_user.id)
    if subject:
        query = query.filter_by(subject=resolve_subject(subject))
    
    sessions = query.order_by(TutorSession.created_at.desc()).limit(3).all()
    
    result = []
    for s in sessions:
        result.append({
            'session_id': s.id,
            'subject': s.subject,
            'created_at': s.created_at.isoformat() if s.created_at else None,
            'messages': [{'role': 'assistant', 'content': '（历史消息已省略）'}]
        })
    
    return jsonify(result)
