"""
画像测评智能体 - Agent 1
功能：基于学校层次+学科+问卷生成学习画像，8维度评估
"""
import json, logging
from config import LEVELS, DIMENSIONS, SUBJECTS
from utils import call_llm, call_llm_json
logger = logging.getLogger(__name__)

# ===== Agent 1: 画像测评智能体 =====
class ProfilingAgent:
    """画像测评：基于学校层次+学科+问卷生成学习画像"""
    
    def generate_questions(self, subject):
        """生成分层问卷题目"""
        subject_name = SUBJECTS.get(subject, subject)
        questions = [
            {
                "id": 1, "dimension": "knowledge",
                "question": f"你对{subject_name}的基础知识了解如何？",
                "type": "choice",
                "options": [
                    {"value": 0, "label": "从未接触过"},
                    {"value": 25, "label": "知道一些基本概念"},
                    {"value": 50, "label": "能理解大部分基础知识"},
                    {"value": 75, "label": "掌握扎实，能运用自如"},
                    {"value": 100, "label": "非常熟练，能教授他人"},
                ]
            },
            {
                "id": 2, "dimension": "understanding",
                "question": f"当遇到{subject_name}的复杂概念时，你通常如何？",
                "type": "choice",
                "options": [
                    {"value": 0, "label": "完全看不懂"},
                    {"value": 25, "label": "需要查资料才能理解"},
                    {"value": 50, "label": "能理解但需要时间"},
                    {"value": 75, "label": "能快速理解并运用"},
                    {"value": 100, "label": "能举一反三，发现深层联系"},
                ]
            },
            {
                "id": 3, "dimension": "application",
                "question": f"你用{subject_name}的知识解决过实际问题吗？",
                "type": "choice",
                "options": [
                    {"value": 0, "label": "从未实践过"},
                    {"value": 25, "label": "做过简单练习"},
                    {"value": 50, "label": "完成过一些项目"},
                    {"value": 75, "label": "独立完成过复杂项目"},
                    {"value": 100, "label": "有丰富的实战经验"},
                ]
            },
            {
                "id": 4, "dimension": "analysis",
                "question": f"给你一个{subject_name}的开放问题，你通常如何？",
                "type": "choice",
                "options": [
                    {"value": 0, "label": "不知道从哪里入手"},
                    {"value": 25, "label": "能想到一些可能的方案"},
                    {"value": 50, "label": "能分析问题并提出解决思路"},
                    {"value": 75, "label": "能系统分析并给出优化方案"},
                    {"value": 100, "label": "能创造性解决，提出创新方案"},
                ]
            },
            {
                "id": 5, "dimension": "creativity",
                "question": f"你在{subject_name}学习中的创新表现如何？",
                "type": "choice",
                "options": [
                    {"value": 0, "label": "按部就班学习"},
                    {"value": 25, "label": "偶尔有自己的想法"},
                    {"value": 50, "label": "经常尝试不同的方法"},
                    {"value": 75, "label": "能改进现有方案"},
                    {"value": 100, "label": "常有创新性突破"},
                ]
            },
            {
                "id": 6, "dimension": "self_learning",
                "question": "你的自主学习能力如何？",
                "type": "choice",
                "options": [
                    {"value": 0, "label": "需要老师全程指导"},
                    {"value": 25, "label": "能跟着教程学习"},
                    {"value": 50, "label": "能自主查找资料学习"},
                    {"value": 75, "label": "能制定计划并执行"},
                    {"value": 100, "label": "有高效的自学方法论"},
                ]
            },
            {
                "id": 7, "dimension": "pace",
                "question": "你的学习节奏是？",
                "type": "choice",
                "options": [
                    {"value": 0, "label": "需要大量时间慢慢消化"},
                    {"value": 25, "label": "按部就班，循序渐进"},
                    {"value": 50, "label": "学习速度中等偏快"},
                    {"value": 75, "label": "学习效率高，吸收快"},
                    {"value": 100, "label": "一目十行，快速掌握"},
                ]
            },
            {
                "id": 8, "dimension": "cognitive",
                "question": "你平时的学习深度如何？",
                "type": "choice",
                "options": [
                    {"value": 0, "label": "停留在记忆层面"},
                    {"value": 25, "label": "能理解基本概念"},
                    {"value": 50, "label": "能分析比较不同概念"},
                    {"value": 75, "label": "能评价和批判性思考"},
                    {"value": 100, "label": "能创造新知识体系"},
                ]
            },
        ]
        return questions
    
    def analyze_assessment(self, answers, subject, school_tier=None):
        """分析测评结果，计算打分和水平等级（LLM驱动）"""
        # 先用原始分数统计
        raw_scores = {dim["id"]: [] for dim in DIMENSIONS}
        # 同时记录每题详情，供LLM差异化评分
        answer_details = []
        for qid, answer in answers.items():
            if isinstance(answer, dict) and 'value' in answer:
                q = self.find_question_by_id(qid, subject)
                if q:
                    dim = q["dimension"]
                    raw_scores.setdefault(dim, []).append(answer["value"])
                    answer_details.append({
                        'question_id': qid,
                        'question': q.get('question', ''),
                        'dimension': dim,
                        'self_score': answer['value']
                    })
            elif isinstance(answer, (int, float)):
                raw_scores.setdefault("knowledge", []).append(answer)
                answer_details.append({
                    'question_id': qid,
                    'question': '',
                    'dimension': 'knowledge',
                    'self_score': answer
                })
        
        raw_avg = {k: round(sum(v)/len(v)) for k, v in raw_scores.items() if v}
        subject_name = SUBJECTS.get(subject, subject)
        
        # 尝试 LLM 智能分析（传入每题详情支持差异化评分）
        llm_succeeded = False
        try:
            dim_name_map = {d['id']: d['name'] for d in DIMENSIONS}
            per_question_summary = '\n'.join([
                f"第{d['question_id']}题（{dim_name_map.get(d['dimension'], d['dimension'])}）自评{d['self_score']}分：{d['question'][:40]}"
                for d in answer_details
            ]) if answer_details else '(无每题详情)'
            prompt = (
                f"你是一名教育测评专家，分析以下学生的学科测评数据，给出各维度分数（0-100）。\n"
                f"学科：{subject_name}\n"
                f"学校层次：{school_tier or '未知'}\n\n"
                f"=== 每题自评详情 ===\n"
                f"{per_question_summary}\n\n"
                f"=== 维度平均分 ===\n"
                f"{json.dumps(raw_avg, ensure_ascii=False)}\n\n"
                f"维度定义：{json.dumps([{'id': d['id'], 'name': d['name'], 'desc': d.get('desc','')} for d in DIMENSIONS], ensure_ascii=False)}\n\n"
                f"请给出最终各维度评分（0-100整数），注意：\n"
                f"1. 不同维度的评分应体现差异化——学生可能在某个维度表现好、另一个维度表现差\n"
                f"2. 参考每题详情中的自评值和题目内容进行判断\n"
                f"3. 综合调整学校层次加成和测评表现\n"
                f"输出JSON ONLY：{{'dimension_scores': {{'knowledge': int, 'understanding': int, 'application': int, 'analysis': int, 'creativity': int, 'self_learning': int, 'pace': int, 'cognitive': int}}, 'summary': 'str'}}"
            )
            parsed = call_llm_json("你是一个严格的教育测评专家，只输出JSON，不要其他文字。", prompt, agent_name='ProfilingAgent')
            if parsed:
                dimension_scores = parsed.get('dimension_scores', raw_avg.copy())
                summary = parsed.get('summary', '')
                llm_succeeded = True
            else:
                raise ValueError("LLM JSON parse failed")
        except Exception as e:
            logger.warning(f"[ProfilingAgent] LLM分析失败，使用原始分数: {e}")
        
        if not llm_succeeded:
            # 降级：基于每题分数差异来拉开维度间的区分度
            if raw_avg:
                dimension_scores = {}
                for dim_id, scores in raw_scores.items():
                    if len(scores) >= 2:
                        # 方差越大说明该维度内题目差异大，用加权平均
                        mean = sum(scores) / len(scores)
                        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
                        std = variance ** 0.5
                        # 最终得分 = 平均分 + 方差偏移（差异越大的维度得分越极端）
                        adjusted = mean + std * 0.3 * (1 if mean >= 50 else -1)
                        dimension_scores[dim_id] = min(100, max(0, round(adjusted)))
                    elif scores:
                        dimension_scores[dim_id] = round(scores[0])
                    else:
                        dimension_scores[dim_id] = 50
            else:
                dimension_scores = {d['id']: 50 for d in DIMENSIONS}
            summary = ""

        # 补全缺失维度
        for dim in DIMENSIONS:
            dimension_scores.setdefault(dim['id'], 50)
        
        valid_scores = [v for v in dimension_scores.values() if isinstance(v, (int, float)) and v > 0]
        total_score = round(sum(valid_scores) / len(valid_scores)) if valid_scores else 50
        level = self.determine_level(total_score)
        level_desc = summary or self.get_level_description(level, dimension_scores, subject)
        
        return {
            "total_score": total_score,
            "level": level,
            "dimension_scores": dimension_scores,
            "feedback": level_desc,
            "school_tier": school_tier
        }
    
    def find_question_by_id(self, qid, subject):
        questions = self.generate_questions(subject)
        for q in questions:
            if q["id"] == int(qid):
                return q
        return None
    
    def determine_level(self, score):
        """根据分数确定水平等级"""
        for level in LEVELS:
            min_s, max_s = level["score_range"]
            if min_s <= score <= max_s:
                return level
        return LEVELS[0]
    
    def get_level_description(self, level, dim_scores, subject):
        """生成测评反馈"""
        subject_name = SUBJECTS.get(subject, subject)
        weak_dims = [DIMENSIONS[i]["name"] for i, (k, v) in enumerate(dim_scores.items()) if v < 40]
        strong_dims = [DIMENSIONS[i]["name"] for i, (k, v) in enumerate(dim_scores.items()) if v >= 70]
        
        feedback = f"综合评分 {dim_scores.get('knowledge', 50)}分，评定为「{level['name']}」水平。"
        
        if weak_dims:
            feedback += f" 薄弱环节：{'、'.join(weak_dims)}，建议重点加强。"
        if strong_dims:
            feedback += f" 优势领域：{'、'.join(strong_dims)}，继续保持。"
        
        feedback += f" {level['desc']}"
        
        return feedback

profiling_agent = ProfilingAgent()

