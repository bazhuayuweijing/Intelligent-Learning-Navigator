"""
资源推荐智能体 - Agent 2
功能：基于测评结果，从资源库推荐+AI生成个性化资源
"""
import json, random, logging
from config import SUBJECTS
from utils import call_llm, call_llm_json
from recommender import recommend, SCHOOL_TIERS, RESOURCE_DB
logger = logging.getLogger(__name__)

# ===== Agent 2: 资源推荐智能体 =====
class ResourceAgent:
    """基于测评结果，从资源库推荐+AI生成个性化资源"""
    
    def recommend(self, level_id, subject, school_tier=None, count=6):
        """推荐资源"""
        subject_name = SUBJECTS.get(subject, subject)
        
        # 先用原recommender的资源
        rec_result = recommend(subject_name, school_tier or "普通本科")
        
        # 解析推荐结果
        resources = []
        
        # 从标准资源库拿
        from recommender import RESOURCE_DB
        if subject_name in RESOURCE_DB:
            subject_resources = RESOURCE_DB[subject_name]
            random.shuffle(subject_resources)
            for r in subject_resources[:count]:
                resources.append({
                    "type": r.get("type", "课程"),
                    "title": r.get("name", ""),
                    "source": r.get("source", ""),
                    "level": r.get("level", ""),
                    "level_id": level_id,
                    "content": f"推荐{r.get('type', '资源')}：{r.get('name', '')} - {r.get('source', '')}",
                    "tags": [subject, r.get("level", "")]
                })
        
        # 加一些AI特有的资源
        ai_picks = self._get_ai_resources(subject_name, level_id, school_tier)
        resources.extend(ai_picks)
        
        return resources[:count + 3]
    
    def _get_ai_resources(self, subject_name, level_id, school_tier):
        """AI精选资源（LLM动态生成）"""
        level_names = {1: "入门级", 2: "基础级", 3: "进阶级", 4: "大神级"}
        level_name = level_names.get(level_id, "基础级")
        
        try:
            prompt = (
                f"你是一名学习资源推荐专家，为一名{subject_name}学习者推荐个性化学习资源。\n"
                f"- 学科：{subject_name}\n"
                f"- 当前水平：{level_name}（Level {level_id}/4）\n"
                f"- 学校层次：{school_tier or '未知'}\n\n"
                f"请推荐3个适合该学生的优质资源（课程/书籍/项目/工具），要求：\n"
                f"1. 资源和{subject_name}强相关\n"
                f"2. 难度匹配{level_name}水平\n"
                f"3. 包含真实存在的知名资源\n"
                f"4. 每个资源有具体标题、来源和推荐理由\n\n"
                f"输出JSON ONLY（数组）：\n"
                f"[{{\"type\": \"课程|书籍|项目|工具\", \"title\": \"具体标题\", \"source\": \"来源/平台\", \"level\": \"{level_name}\", \"content\": \"推荐理由（20-50字）\"}}]"
            )
            parsed = call_llm_json("你是一个学习资源推荐专家，严格按JSON格式输出。", prompt, allow_list=True, agent_name='ResourceAgent')
            if isinstance(parsed, list):
                for r in parsed:
                    r['level_id'] = level_id
                    r['tags'] = [subject_name, r.get('level', '')]
                return parsed
        except Exception as e:
            logger.warning(f"[ResourceAgent] LLM推荐失败，使用默认资源: {e}")
        
        return [{"type": "课程", "title": f"精品课程 - {subject_name} {level_name}", "source": "智慧树", "level": level_name, "level_id": level_id, "content": f"适合{level_name}水平学习{subject_name}。", "tags": [subject_name, level_name]}]

resource_agent = ResourceAgent()

