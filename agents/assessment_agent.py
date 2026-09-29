"""
学习评估智能体 - Agent 5
功能：学习效果评估与动态调级
"""
import json, random, logging
from config import LEVELS, SUBJECTS, DIMENSIONS
from models import Evaluation
from utils import call_llm, call_llm_json
logger = logging.getLogger(__name__)

# ===== Agent 5: 学习评估智能体 =====
class AssessmentAgent:
    """学习效果评估与动态调级"""
    
    def evaluate(self, answers, current_level, subject):
        """评估学习效果（LLM驱动）"""
        correct_count = sum(1 for a in answers if isinstance(a, dict) and a.get('correct'))
        total = len(answers) if answers else 1
        accuracy = round(correct_count / total * 100)
        
        current_level_obj = next((l for l in LEVELS if l["id"] == current_level), LEVELS[0])
        subject_name = SUBJECTS.get(subject, subject)
        
        # LLM多维评估
        try:
            prompt = (
                f"你是一名学习评估专家，评估以下学生的学习表现。\n"
                f"学科：{subject_name}\n"
                f"当前水平：{current_level_obj['name']}（Level {current_level}/4）\n"
                f"答题结果：{total}题中答对{correct_count}题（正确率{accuracy}%）\n\n"
                f"请从5个维度评分（0-100整数），并给出调级建议：\n"
                f"- knowledge（知识掌握）：基础概念和原理的理解\n"
                f"- understanding（理解深度）：对知识的融会贯通\n"
                f"- application（应用能力）：将知识应用于实际\n"
                f"- analysis（分析评价）：分析和判断能力\n"
                f"- creativity（创新思维）：独立思考和创新能力\n\n"
                f"调级规则：\n"
                f"- 综合≥80分且当前<4级 → upgrade\n"
                f"- 综合≤30分且当前>1级 → downgrade\n"
                f"- 其他情况 → stay\n\n"
                f"输出JSON ONLY：{{\"dimensions\": {{\"knowledge\": int, \"understanding\": int, \"application\": int, \"analysis\": int, \"creativity\": int}}, \"feedback\": \"综合评语（50字内）\"}}"
            )
            parsed = call_llm_json("你是一个严格的学习评估专家。只输出JSON。", prompt, agent_name='AssessmentAgent')
            if parsed:
                dimension_scores = parsed.get('dimensions', {})
                feedback_text = parsed.get('feedback', '')
            else:
                raise ValueError("LLM JSON parse failed")
        except Exception as e:
            logger.warning(f"[AssessmentAgent] LLM评估失败，使用默认评分: {e}")
            dimension_scores = {
                "knowledge": min(100, accuracy + random.randint(-5, 5)),
                "understanding": min(100, accuracy + random.randint(-10, 5)),
                "application": min(100, accuracy + random.randint(-10, 5)),
                "analysis": min(100, accuracy + random.randint(-10, 10)),
                "creativity": min(100, accuracy + random.randint(-5, 10)),
            }
            feedback_text = ""
        
        weights = {"knowledge": 0.25, "understanding": 0.2, "application": 0.25, "analysis": 0.15, "creativity": 0.15}
        overall = round(sum(dimension_scores.get(k, accuracy) * weights[k] for k in weights))
        
        # 动态调级决策
        action = "stay"
        new_level = current_level
        if overall >= 80 and current_level < 4:
            action = "upgrade"
            new_level = current_level + 1
        elif overall < 30 and current_level > 1:
            action = "downgrade"
            new_level = current_level - 1
        
        new_level_obj = next((l for l in LEVELS if l["id"] == new_level), current_level_obj)
        
        # 生成LLM反馈
        suggestions = self._generate_suggestions(dimension_scores)
        feedback = feedback_text or f"正确率{accuracy}%，综合评分{overall}分。"
        if action == 'upgrade':
            feedback += " 已达到升级条件，建议挑战更高层次！"
        elif action == 'downgrade':
            feedback += " 当前层次尚有困难，建议先巩固基础。"
        
        return {
            "overall": overall,
            "accuracy": accuracy,
            "dimensions": dimension_scores,
            "action": action,
            "from_level": current_level_obj["name"],
            "from_level_id": current_level,
            "to_level": new_level_obj["name"] if new_level_obj else current_level_obj["name"],
            "to_level_id": new_level,
            "feedback": feedback,
            "suggestions": suggestions
        }
    
    def _generate_suggestions(self, dim_scores):
        suggestions = []
        dim_names = {d['id']: d['name'] for d in DIMENSIONS}
        for k, v in dim_scores.items():
            dim_name = dim_names.get(k, k)
            if v < 40:
                suggestions.append(f"加强{dim_name}：建议多做基础练习")
            elif v < 60:
                suggestions.append(f"提升{dim_name}：尝试更复杂的应用")
        if not suggestions:
            suggestions.append("继续保持，挑战更难内容")
        return suggestions[:3]
    
    def get_progress(self, user_id, subject):
        """获取学习进步趋势"""
        evaluations = Evaluation.query.filter_by(
            user_id=user_id, subject=subject
        ).order_by(Evaluation.created_at).all()
        
        if not evaluations:
            return None
        
        return {
            "scores": [e.overall_score for e in evaluations],
            "dates": [e.created_at.strftime("%m-%d") for e in evaluations],
            "levels": [e.previous_level or 1 for e in evaluations],
            "count": len(evaluations),
            "latest": evaluations[-1].overall_score,
            "first": evaluations[0].overall_score,
            "improvement": round(evaluations[-1].overall_score - evaluations[0].overall_score, 1),
        }

assess_agent = AssessmentAgent()
