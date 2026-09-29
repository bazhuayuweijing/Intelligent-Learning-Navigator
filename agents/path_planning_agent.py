"""
路径规划智能体 - Agent 3
功能：AI规划从当前到下一层次的学习路径
"""
import json, logging
from config import LEVELS, SUBJECTS, DIMENSIONS
from utils import call_llm, call_llm_json
logger = logging.getLogger(__name__)

# ===== Agent 3: 路径规划智能体 =====
class PathPlanningAgent:
    """AI规划从当前到下一层次的学习路径"""
    
    def plan_path(self, level_id, subject, dimension_scores=None):
        """生成学习路径（LLM驱动）"""
        level = None
        for l in LEVELS:
            if l["id"] == level_id:
                level = l
                break
        if not level:
            level = LEVELS[0]
        
        next_level_obj = None
        for l in LEVELS:
            if l["id"] == level_id + 1:
                next_level_obj = l
                break
        
        subject_name = SUBJECTS.get(subject, subject)
        weak_names = []
        if dimension_scores:
            dim_map = {d['id']: d['name'] for d in DIMENSIONS}
            for k, v in dimension_scores.items():
                if v < 40:
                    weak_names.append(dim_map.get(k, k))
        
        # LLM生成个性化路径
        try:
            dims_str = json.dumps({k: v for k, v in (dimension_scores or {}).items() if isinstance(v, (int, float))}, ensure_ascii=False)
            prompt = (
                f"你是一名学习路径规划专家，为一名{subject_name}学生定制学习方案。\n"
                f"- 当前水平：{level['name']}（Level {level_id}）\n"
                f"- 目标水平：{next_level_obj['name'] if next_level_obj else '提升一阶'}（Level {level_id + 1 if next_level_obj else level_id}）\n"
                f"- 各维度分数：{dims_str}\n"
                f"- 薄弱环节：{'、'.join(weak_names[:3]) or '无明显短板'}\n\n"
                f"请规划一个分阶段学习路径（3-4个阶段），每个阶段包含标题、建议时长、学习目标、具体内容和每日练习建议。\n"
                f"路径要个性化：针对薄弱环节设计强化内容，整体让学习者能从当前水平提升到目标水平。\n\n"
                f"输出JSON ONLY（不要markdown包围）：\n"
                f"{{\"stages\": [{{\"stage\": int, \"title\": \"阶段标题\", \"duration\": \"建议时长\", \"objective\": \"学习目标\", \"contents\": [\"具体内容1\", \"具体内容2\"], \"practice\": \"每日练习建议\"}}], \"total_duration\": \"总时长\", \"daily_suggestion\": \"每日建议\"}}"
            )
            parsed = call_llm_json("你是一个学习路径规划专家，严格按JSON输出。", prompt, agent_name='PathPlanningAgent')
            if parsed:
                stages = parsed.get('stages', [])
                if stages:
                    return {
                            "stages": stages,
                            "total_duration": parsed.get('total_duration', '4-8周'),
                            "from_level": level["name"],
                            "to_level": next_level_obj["name"] if next_level_obj else level["name"],
                            "improvement_focus": f"重点提升：{'、'.join(weak_names[:3])}" if weak_names else "全面系统提升",
                            "daily_suggestion": parsed.get('daily_suggestion', '每天1-2小时系统学习')
                        }
        except Exception as e:
            logger.warning(f"[PathPlanningAgent] LLM路径失败，使用默认模板: {e}")
        
        # 回退：默认4阶段模板
        stages = [
            {"stage": 1, "title": f"基础巩固 - {subject_name}核心概念", "duration": "1-2周", "objective": "夯实基础", "contents": [f"{subject_name}核心概念梳理", "基础练习"], "practice": "每日整理+练习30分钟"},
            {"stage": 2, "title": f"能力提升 - {subject_name}进阶", "duration": "2-3周", "objective": "提升理解与应用", "contents": ["进阶知识点", "案例分析"], "practice": "每周一个小项目"},
            {"stage": 3, "title": f"实战强化", "duration": "2-3周", "objective": "通过实战巩固", "contents": ["中型项目", "代码审查"], "practice": "项目驱动"},
        ]
        if next_level_obj:
            stages.append({"stage": 4, "title": f"冲刺{next_level_obj['name']}", "duration": "1-2周", "objective": f"达到{next_level_obj['name']}水平", "contents": ["核心能力训练", "模拟测试"], "practice": "强化训练"})
        
        return {
            "stages": stages,
            "total_duration": "6-10周",
            "from_level": level["name"],
            "to_level": next_level_obj["name"] if next_level_obj else level["name"],
            "improvement_focus": f"重点提升：{'、'.join(weak_names[:3])}" if weak_names else "全面系统提升",
            "daily_suggestion": f"每天学习1-2小时，周末安排项目实践。"
        }

path_agent = PathPlanningAgent()

