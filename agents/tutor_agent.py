"""
智能辅导智能体 - Agent 4
功能：AI辅导员，实时答疑，引导式教学（苏格拉底教学法）
"""
import re, logging
from config import LEVELS, SUBJECTS
from utils import call_llm
logger = logging.getLogger(__name__)

# ===== Agent 4: 智能辅导智能体 =====
class TutorAgent:
    """AI辅导员：实时答疑，引导式教学"""
    
    def answer(self, question, subject, level_id=1, history=None):
        """回答问题"""
        level_name = "基础级"
        for l in LEVELS:
            if l["id"] == level_id:
                level_name = l["name"]
                break
        
        subject_name = SUBJECTS.get(subject, subject)
        
        # 先用LLM尝试
        system_prompt = f"""你是一名专业耐心的AI学习辅导员，使用苏格拉底教学法引导学生思考。
当前学科：{subject_name}
学生水平：{level_name}

辅导原则：
1. 先肯定学生的提问
2. 根据{level_name}水平调整讲解深度
3. 用具体例子帮助理解
4. 给出巩固练习题
5. 以追问引导思考"""
        
        llm_result = call_llm(system_prompt, question)
        if llm_result:
            return {
                "answer": llm_result,
                "key_points": self.extract_key_points(llm_result),
                "is_ai": True
            }
        
        # 降级到模拟回答
        return self._mock_answer(question, subject_name, level_name)
    
    def _mock_answer(self, question, subject_name, level_name):
        """模拟回答"""
        question_lower = question.lower()
        answer = ""
        key_points = []
        
        if "什么是" in question or "概念" in question or "定义" in question:
            answer = f"这是个很好的概念性问题！\n\n在「{subject_name}」中，你提到的这个概念可以这样理解：\n\n首先，我们需要从最基本的定义说起...\n\n举个例子帮助理解：假设你正在学习一个具体的应用场景...\n\n✨ **核心要点**：理解这个概念的关键在于掌握它的本质特征和与其他概念的区别。"
            key_points = ["理解本质定义", "掌握核心特征", "注意与相似概念的区别"]
        elif "怎么" in question or "如何" in question or "方法" in question:
            answer = f"这个问题问得好！「如何做」是学习中很关键的环节。\n\n**步骤一**：先确保理解前置知识\n**步骤二**：按照规范的流程操作\n**步骤三**：多练习，在实践中理解\n\n💡 建议你先尝试自己动手做一遍，遇到具体困难再针对性地提问。"
            key_points = ["明确步骤流程", "动手实践", "边做边理解"]
        elif "区别" in question or "对比" in question or "vs" in question_lower:
            answer = f"很好的对比性问题！让我从几个维度来分析：\n\n**1. 本质不同**：它们关注的核心问题不同\n**2. 应用场景**：适用的场景有所区别\n**3. 优缺点**：各有擅长的领域\n\n建议你画一个对比表格来加深理解。"
            key_points = ["本质差异", "应用场景区分", "优缺对比"]
        elif "代码" in question or "编程" in question or "实现" in question:
            answer = f"编程实践是最好的学习方式！\n\n让我给你一个简单的示例框架：\n\n```\n# 这是实现思路\n# 1. 先定义输入/输出\n# 2. 按照算法逻辑实现\n# 3. 测试边界情况\n```\n\n建议你先自己尝试写一遍，遇到具体报错再回来问我。\n\n✏️ **练习**：尝试修改参数，观察输出变化。"
            key_points = ["理清逻辑思路", "动手编码", "测试验证"]
        else:
            answer = f"这是个值得深入探讨的问题！\n\n在「{subject_name}」的学习中，{question}涉及多个层面：\n\n**1. 基础知识层面**：需要先理解相关核心概念\n**2. 应用层面**：在实际场景中的使用方式\n**3. 拓展层面**：与其他知识的关联\n\n💭 你能先说说你对这个问题的初步理解吗？这样我可以更有针对性地帮你。"
            key_points = ["基础知识", "实际应用", "拓展思考"]
        
        return {
            "answer": answer,
            "key_points": key_points,
            "practice": f"请尝试用{subject_name}的知识，从实际角度分析这个问题。",
            "follow_up": "你理解了吗？需要我换个角度解释吗？",
            "is_ai": False
        }
    
    def extract_key_points(self, text):
        """从AI回答中提取关键点"""
        points = re.findall(r'(?:关键|重点|要点|核心)\s*[：:]\s*([^。\n]+)', text)
        if not points:
            points = re.findall(r'(?:[\d一二三四五六七八九十]+[.、．])\s*([^。\n]+)', text)
            points = points[:3]
        if not points:
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 5]
            points = [l[:30] for l in lines[:3]]
        return points[:3]

tutor_agent = TutorAgent()

