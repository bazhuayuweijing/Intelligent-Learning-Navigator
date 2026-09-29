"""
多智能体资源生成系统
6+1个专业Agent协同工作，生成多模态个性化学习资源

Agent架构:
  Coordinator → 理解需求 → 分发到专业Agent → 整合返回
    ├── DocAgent            → 课程讲解文档
    ├── MindMapAgent        → 知识思维导图 (Mermaid)
    ├── QuizAgent           → 多样化练习题库
    ├── CaseAgent           → 实操案例/代码
    ├── ResourceRecommenderAgent → 视频/书籍/论文推荐
    └── TrapExamGenerator   → 认知弱点克星题
"""
import json, random
from datetime import datetime


class BaseGeneratorAgent:
    """所有生成Agent的基类"""
    name = "base"
    description = ""

    def generate(self, context: dict) -> dict:
        raise NotImplementedError


# ===== Agent: 课程文档生成 =====
class DocAgent(BaseGeneratorAgent):
    name = "document"
    description = "生成专业课程讲解文档"

    def generate(self, context: dict) -> dict:
        subject = context.get("subject", "computer_science")
        subject_name = context.get("subject_name", subject)
        level = context.get("level", 1)
        topic = context.get("topic", subject_name)
        weak_points = context.get("weak_points", [])
        learning_goal = context.get("learning_goal", f"系统学习{subject_name}")

        level_names = {1: "基础入门", 2: "中等进阶", 3: "高级深化", 4: "大神专题"}
        level_name = level_names.get(level, "基础入门")

        # ===== 个性化画像感知调整 =====
        profile = context.get("student_profile", {})
        if profile.get("has_profile"):
            dim_scores = profile.get("dimension_scores", {})
            cognitive_style = profile.get("cognitive_style", "综合型")
            profile_weak_points = profile.get("weak_points", [])
            
            # 根据认知风格调整文档风格
            if cognitive_style in ("实践驱动型", "视听学习型"):
                learning_goal = f"{learning_goal}（多提供实际案例和可操作步骤）"
                # 追加实践导向的文档要求
                context["_style_hint"] = "实践导向。多用具体代码/案例展示，每节必跟至少一个实际应用场景。少大段理论推导，多操作步骤和效果截图描述。"
            elif cognitive_style == "系统理论型":
                context["_style_hint"] = "理论导向。强调概念的定义、分类和内在逻辑关系。用类比帮助理解抽象概念，提供完整知识框架和术语表。"
            elif cognitive_style == "阅读自学型":
                context["_style_hint"] = "自学导向。结构清晰层次分明，每节含学习目标和自测问题。提供扩展阅读指引以备深入。"
            
            # 根据薄弱维度重点强化对应内容
            if "application" in profile_weak_points:
                context["_weakness_focus"] = "application"
                learning_goal = f"{learning_goal}（重点加强实践应用能力训练）"
            elif "understanding" in profile_weak_points:
                context["_weakness_focus"] = "understanding"
                learning_goal = f"{learning_goal}（重点加强概念理解和深度分析）"

        return {
            "type": "document",
            "title": f"《{subject_name}·{topic}》{level_name}讲解",
            "format": "markdown",
            "generated_at": datetime.utcnow().isoformat(),
            "content": self._build_doc(subject_name, topic, level_name, weak_points, learning_goal, subject, context),
            "metadata": {
                "subject": subject,
                "level": level,
                "topic": topic,
                "recommended_duration": f"{random.randint(2,6)}小时",
                "difficulty": level_name
            }
        }

    def _build_doc(self, subject_name, topic, level, weak_points, goal, subject_key=None, context=None):
        """构建文档内容（LLM优先，失败回退增强模板）"""
        context = context or {}
        try:
            from utils import call_llm, call_llm_json
            try:
                from knowledge_base import kb
                kb_key = subject_key.lower().replace(' ', '_') if subject_key else subject_name.lower().replace(' ', '_')
                kb_context = kb.get_context(query=f"{subject_name} {topic} {goal}", subject=kb_key)
            except Exception:
                kb_context = ""
            base_prompt = "你是一名专业的课程设计老师。请根据学科、主题和学生水平生成一份有价值的Markdown学习文档，内容要具体不空泛。语言为中文。"
            sys_prompt = base_prompt + ("\n\n" + kb_context if kb_context else "")
            
            # 注入个性化风格说明
            style_hint = context.get("_style_hint", "")
            weakness_focus = context.get("_weakness_focus", "")
            profile = context.get("student_profile", {})
            
            content_instructions = [
                "1. 核心概念讲解（含定义、前置知识要求、为什么这个概念重要）",
                "2. 知识点精讲（3-4个小节，每节含具体示例或类比）",
                "3. 常见误区分析（针对薄弱点，给出具体纠偏建议和对比表）",
                "4. 阶段学习路线图（分3个阶段，每个阶段配具体动作）",
                "5. 重点总结（5条核心Takeaway）",
            ]
            
            # 根据薄弱维度调整内容结构
            if weakness_focus == "application":
                content_instructions.insert(2, "- 每个知识点必须紧跟一个实际应用案例或代码片段")
                content_instructions.insert(3, "- 增加「动手练习」环节，每节至少1道实践题")
            elif weakness_focus == "understanding":
                content_instructions.insert(2, "- 每个概念必须配类比说明，避免纯定义堆砌")
                content_instructions.insert(3, "- 增加概念对比表，突出易混淆点区分")
            
            # 根据学习风格调整文档结构
            if profile.get("has_profile"):
                dim_scores = profile.get("dimension_scores", {})
                if dim_scores.get("application", 50) < 40:
                    content_instructions.append("- 增加「一图流」概念图示描述（文字版），帮助建立直观印象")
                if dim_scores.get("creativity", 50) < 40:
                    content_instructions.append("- 增加开放思考题，鼓励学生跳出框框思考")
            
            user_prompt = (
                f"学科：{subject_name}\n"
                f"主题：{topic}\n"
                f"学生水平：{level}\n"
                f"学习目标：{goal}\n"
                f"薄弱点：{weak_points}\n"
                f"风格说明：{style_hint}\n"
                "\n"
                "请包含以下内容：\n"
                + "\n".join(content_instructions) + "\n"
                f"难度适配{level}水平，长度中等（5-10分钟阅读量）。"
            )
            llm_result = call_llm(sys_prompt, user_prompt)
            if llm_result and len(llm_result) > 300:
                return llm_result
        except Exception as e:
            print(f"[DocAgent] LLM失败，使用增强模板: {e}")

        # --- 增强的回退模板（不再是简陋的骨架，而是特征完整的文档） ---
        weak_section = ""
        if weak_points:
            weak_section = "\n".join(f"- ❌ {w}" for w in weak_points[:3])
            weak_section = f"\n### 常见误区与纠偏\n针对以下薄弱环节，逐一给出纠正建议：\n{weak_section}\n"

        return f"""# {topic} - {level}学习指南

> 学习目标：{goal}
> 难度等级：{level}
> 建议用时：{random.randint(2,5)}小时

---

## 一、为什么学{topic}？

在{subject_name}领域中，{topic}处于核心地位。理解{topic}能够帮助你：
- 建立{subject_name}的知识骨架，后续所有进阶内容都建立在此之上
- 掌握{subject_name}领域通用的分析框架和思维方式
- 为实际项目中的{subject_name}应用打下坚实的基础

**前置知识要求**：{subject_name}的基本术语和概念，建议先花10分钟温习基础术语。

---

## 二、核心概念精讲

### 2.1 什么是{topic}

{topic}是{subject_name}中用于描述和分析特定现象/问题的理论框架和方法论集合。它的核心思想可以概括为：通过系统化的方法，将复杂问题分解为可管理的模块，然后逐一攻克。

**类比帮助理解：** 就像盖房子，{topic}提供的是设计蓝图和施工规范——你不需要从零开始想每个细节，而是按照成熟的框架来执行。

### 2.2 {topic}的核心要素

1. **第一性原理**：从最基本的事实和规律出发，不依赖类比或既有结论
2. **模块化思维**：将大问题拆解为独立的小问题，降低复杂度
3. **迭代验证**：不追求一次性完美，而是快速建雏形、测试、改进

### 2.3 {topic}与传统方法的区别

| 维度 | 传统方式 | {topic}方式 |
|------|---------|------------|
| 思维方式 | 经验驱动 | 原理驱动 |
| 问题解决 | 线性流程 | 迭代循环 |
| 适应性 | 固定的 | 动态调整 |
| 复杂度处理 | 简单化 | 分解控制 |

---

## 三、{level}核心知识点

### 基础知识层
- 理解{topic}的基本定义和适用范围
- 掌握核心概念之间的关系
- 能用自己的话复述主要内容

### 进阶理解层
- 分析{topic}在实际场景中的具体应用
- 对比{topic}与其他相关理论框架的异同
- 识别{topic}的适用边界和局限{weak_section}

### 实践应用层
- 在小型项目中实践{topic}的核心方法
- 记录实践中的问题和反思
- 逐步建立自己的{topic}知识体系

---

## 四、阶段性学习路线

### 阶段一：建立基础（第1-2天）
- 通读本文档，标记不理解的地方
- 查找{subject_name}基础术语，补齐前置知识
- 尝试用自己的话总结3个核心概念

### 阶段二：深化理解（第3-5天）
- 针对每个核心概念，找2-3个实际案例对照
- 完成配套练习题（建议先做选择题，再做简答题）
- 绘制{topic}知识点思维导图，检查知识盲区

### 阶段三：综合应用（第1-2周）
- 完成一个与{topic}相关的小项目
- 将所学内容整理为笔记/博客
- 尝试向他人讲解{topic}核心内容（费曼学习法）

---

## 五、重点总结

1. **{topic}**的核心在于**将复杂问题分解为可控模块**的系统化方法
2. 理解{topic}的前提是掌握{subject_name}基础概念——不要跳过前置知识
3. 学习的重点是**应用而不是记忆**，多做练习比多读文档有效
4. 遇到不懂的概念时，先用类比理解本质，再深究细节
5. 持续把新知识和已有知识连接起来，形成知识网络而非孤立点
"""


class MindMapAgent(BaseGeneratorAgent):
    name = "mindmap"
    description = "生成知识思维导图"

    def generate(self, context: dict) -> dict:
        subject = context.get("subject", "computer_science")
        subject_name = context.get("subject_name", subject)
        level = context.get("level", 1)
        topic = context.get("topic", subject_name)
        weak_points = context.get("weak_points", [])

        # ===== 个性化画像感知调整 =====
        profile = context.get("student_profile", {})
        if profile.get("has_profile"):
            cognitive_style = profile.get("cognitive_style", "综合型")
            profile_weak = profile.get("weak_points", [])
            if "analysis" in profile_weak or "understanding" in profile_weak:
                context["_mindmap_depth"] = 3  # 细化到三级节点
            elif cognitive_style == "系统理论型":
                context["_mindmap_depth"] = 3
            else:
                context["_mindmap_depth"] = 2

        return {
            "type": "mindmap",
            "title": f"{subject_name}·{topic}知识导图",
            "format": "mermaid",
            "generated_at": datetime.utcnow().isoformat(),
            "mermaid": self._build_mermaid(subject_name, topic, level),
            "outline": self._build_outline(subject_name, topic, level),
            "metadata": {
                "subject": subject,
                "level": level,
                "topic": topic
            }
        }

    def _build_mermaid(self, subject_name, topic, level):
        try:
            from utils import call_llm, call_llm_json
            sys_prompt = "你是一个知识图谱专家，只输出Mermaid代码，不要额外文字。"
            user_prompt = f"""为{topic}课程设计一个Mermaid graph TD格式知识导图。
学科：{subject_name}，难度等级：{level}/4。
根节点叫"{topic}知识体系"，
一级分支：基础概念、核心原理、实践应用、进阶拓展。
每个一级分支下至少3个子节点，子节点名用中文具体内容，不写占位符。
仅输出Mermaid代码，不加```包裹。
"""
            llm_result = call_llm(sys_prompt, user_prompt)
            if llm_result and "graph" in llm_result.lower():
                return llm_result.strip().lstrip("```mermaid").rstrip("```").strip()
        except Exception as e:
            print(f"[MindMapAgent] LLM失败: {e}")
        return self._default_mermaid(topic)

    @staticmethod
    def _default_mermaid(topic):
        return f"""graph TD
    A["{topic}知识体系"] --> B["基础概念"]
    A --> C["核心原理"]
    A --> D["实践应用"]
    A --> E["进阶拓展"]
    B --> B1["定义与本质"]
    B --> B2["发展历程"]
    B --> B3["相关术语"]
    C --> C1["基本原理"]
    C --> C2["核心算法"]
    C --> C3["数学模型"]
    D --> D1["入门示例"]
    D --> D2["典型应用"]
    D --> D3["项目实战"]
    E --> E1["前沿发展"]
    E --> E2["深入研究"]
    E --> E3["跨领域联系"]
"""

    def _build_outline(self, subject, topic, level):
        return [
            {"title": "基础概念", "items": ["定义与本质", "发展历程", "相关术语"]},
            {"title": "核心原理", "items": ["基本原理", "核心算法", "数学模型", "关键公式"]},
            {"title": "实践应用", "items": ["入门示例", "典型应用", "项目实战", "最佳实践"]},
            {"title": "进阶拓展", "items": ["前沿发展", "深入研究", "跨领域联系"]},
        ]


class QuizAgent(BaseGeneratorAgent):
    name = "quiz"
    description = "生成多样化练习题"

    @staticmethod
    def _normalize_choice_answer(parsed: dict) -> dict:
        """将LLM返回的各种格式answer统一归一化为整数索引(0-based)。
        支持: 数字, 字符串数字, 字母A/B/C/D, 选项文本
        """
        ans = parsed.get("answer")
        options = parsed.get("options", [])
        if not options or ans is None:
            return parsed

        idx = None
        # 数字类型
        if isinstance(ans, (int, float)):
            idx = int(ans)
        # 字符串类型
        elif isinstance(ans, str):
            s = ans.strip()
            # 纯数字字符串 "0"-"9"
            if s.isdigit():
                idx = int(s)
            # 单字母 A/B/C/D (大小写)
            elif len(s) == 1 and s.upper() in 'ABCDEFGH':
                idx = ord(s.upper()) - 65
            # "A. xxx" / "A、xxx" / "A xxx" 格式
            elif len(s) >= 2 and s[0].upper() in 'ABCDEFGH' and s[1] in '.、 ':
                idx = ord(s[0].upper()) - 65
            # 选项文本匹配
            else:
                # 尝试与options中的文本匹配
                for i, opt in enumerate(options):
                    # 去除选项前缀后比较
                    opt_clean = opt.strip()
                    opt_text = ' '.join(opt_clean.split()[1:]) if opt_clean and opt_clean[0].upper() in 'ABCDEFGH' else opt_clean
                    ans_text = s.strip()
                    ans_text_clean = ' '.join(ans_text.split()[1:]) if ans_text and ans_text[0].upper() in 'ABCDEFGH' else ans_text
                    if opt_text == ans_text or opt_clean == ans_text or opt_text == ans_text_clean:
                        idx = i
                        break

        # 校验索引有效性
        if idx is not None and 0 <= idx < len(options):
            parsed["answer"] = idx
        elif idx is not None:
            # 索引越界，fallback回原值
            pass

        return parsed

    def generate(self, context: dict) -> dict:
        subject = context.get("subject", "computer_science")
        subject_name = context.get("subject_name", subject)
        level = context.get("level", 1)
        topic = context.get("topic", subject_name)
        count = context.get("question_count", 6)

        # ===== 个性化画像感知调整 =====
        profile = context.get("student_profile", {})
        question_focus = "balanced"
        if profile.get("has_profile"):
            profile_weak = profile.get("weak_points", [])
            dim_scores = profile.get("dimension_scores", {})
            if "application" in profile_weak or dim_scores.get("application", 50) < 40:
                question_focus = "scenario"
            elif "understanding" in profile_weak or dim_scores.get("understanding", 50) < 40:
                question_focus = "concept"
            elif "analysis" in profile_weak:
                question_focus = "compare"
            context["_question_focus"] = question_focus

        return {
            "type": "quiz",
            "title": f"{subject_name}·{topic}配套练习题",
            "format": "json",
            "generated_at": datetime.utcnow().isoformat(),
            "questions": self._generate_questions(subject_name, topic, level, count, context),
            "metadata": {
                "subject": subject,
                "level": level,
                "topic": topic,
                "total_questions": count,
                "question_types": ["选择题", "填空题", "简答题", "编程题"],
                "question_focus": question_focus
            }
        }

    def _generate_questions(self, subject_name, topic, level, count, context=None):
        context = context or {}
        questions = []
        question_focus = context.get("_question_focus", "balanced")
        types_pool = [
            {"type": "choice", "label": "选择题"},
            {"type": "fill", "label": "填空题"},
            {"type": "short_answer", "label": "简答题"},
            {"type": "code", "label": "编程题"},
        ]

        # 根据题型聚焦调整题目类型分布
        if question_focus == "scenario":
            types_pool = [
                {"type": "short_answer", "label": "情景应用题"},
                {"type": "choice", "label": "选择题"},
                {"type": "code", "label": "编程测试题"},
                {"type": "short_answer", "label": "情景应用题"},
            ]
        elif question_focus == "concept":
            types_pool = [
                {"type": "choice", "label": "概念选择题"},
                {"type": "short_answer", "label": "概念辨析题"},
                {"type": "fill", "label": "关键概念题"},
                {"type": "choice", "label": "概念选择题"},
            ]
        elif question_focus == "compare":
            types_pool = [
                {"type": "short_answer", "label": "对比分析题"},
                {"type": "choice", "label": "技术选型题"},
                {"type": "short_answer", "label": "对比分析题"},
                {"type": "fill", "label": "特性比较题"},
            ]

        level_score_map = {1: 10, 2: 15, 3: 20, 4: 25}

        for i in range(count):
            q_meta = types_pool[i % len(types_pool)]
            q_type = q_meta["type"]
            q_label = q_meta["label"]
            q = self._make_question(subject_name, topic, level, q_type, i+1, context)
            # 补充前端需要的字段
            q["label"] = q.get("label") or q_label
            q["score"] = q.get("score") or level_score_map.get(level, 10)
            questions.append(q)

        return questions

    def _make_question(self, subject_name, topic, level, q_type, idx, context=None):
        """生成单个题目（LLM优先，失败回退）"""
        context = context or {}
        type_names = {"choice": "选择题", "fill": "填空题", "short_answer": "简答题", "code": "编程题"}
        type_name = type_names.get(q_type, "选择题")
        
        # 注入个性化出题方向
        question_focus = context.get("_question_focus", "balanced")
        focus_hints = {
            "scenario": "重点考察实际应用能力。选择题和简答题应设置真实场景（如项目中的实际决策、调试场景）。",
            "concept": "重点考察概念理解深度。多出概念辨析、定义解释类题目，干扰项要贴近易混淆概念。",
            "compare": "重点考察分析评价能力。多出技术对比、方案评估、优缺点分析类题目。",
            "balanced": ""
        }
        focus_hint = focus_hints.get(question_focus, "")
        
        try:
            from utils import call_llm, call_llm_json
            sys_prompt = f"你是一个{subject_name}学科的出题老师，生成高质量{type_name}。"
            user_prompt = (
                f"学科：{subject_name}\n"
                f"主题：{topic}\n"
                f"难度：{level}/4级\n"
                f"题型：{type_name}\n"
                f"出题方向：{focus_hint}\n\n"
                "如果是选择题：返回JSON {{\"id\": int, \"question\": \"题干（语义完整的具体问题）\", \"options\": [\"A. \", \"B. \", \"C. \", \"D. \"], \"answer\": 0-3}}\n"
                "如果是填空题：返回JSON {{\"id\": int, \"question\": \"题干（用___表示填空位置）\", \"answer\": \"答案\"}}\n"
                "如果是简答题：返回JSON {{\"id\": int, \"question\": \"题干\", \"answer\": \"参考答案要点\"}}\n"
                "如果是编程题：返回JSON {{\"id\": int, \"question\": \"题干\", \"starter_code\": \"初始代码\", \"answer\": \"参考实现\"}}\n"
                "只输出JSON，不要其他文字。"
            )
            parsed = call_llm_json(sys_prompt, user_prompt, agent_name='QuizAgent')
            if parsed:
                parsed["type"] = q_type
                parsed["subject"] = subject_name
                parsed["topic"] = topic
                parsed["difficulty"] = level
                # 归一化选择题答案为整数索引
                if q_type == 'choice':
                    parsed = self._normalize_choice_answer(parsed)
                return parsed
        except Exception as e:
            print(f"[QuizAgent] LLM出题失败: {e}")

        # --- 增强的回退题库 ---
        fallback_questions = {
            "choice": {
                "question": f"关于{topic}，以下哪个选项最准确地描述了核心概念？",
                "options": [
                    f"A. {topic}是{subject_name}中用于描述和解决问题的系统性方法论",
                    f"B. {topic}等同于{subject_name}的全部内容",
                    f"C. {topic}和{subject_name}没有关系",
                    f"D. {topic}只在特定场景下有意义，通用性不强"
                ],
                "answer": 0
            },
            "fill": {
                "question": f"{topic}的核心思想可以概括为：通过_______的方法，将复杂问题分解为可控模块。",
                "answer": "系统化"
            },
            "short_answer": {
                "question": f"请简述{topic}在{subject_name}领域中的三个主要应用场景，并各举一个具体例子。",
                "answer": f"1. 在教育场景中，{topic}用于个性化学习路径规划（如根据学生画像推荐学习资源）\n2. 在科研场景中，{topic}用于实验设计和数据分析\n3. 在工业场景中，{topic}用于流程优化和自动化"
            },
            "code": {
                "question": f"请编写一个简单的Python函数，实现{topic}相关的基础功能（如数据分析和可视化）。",
                "starter_code": f"# 请在此处编写与{topic}相关的代码\ndef analyze_{topic.lower().replace(' ', '_')}(data):\n    pass",
                "answer": "def analyze_{}(data):\n    results = dict()\n    results['count'] = len(data)\n    results['mean'] = sum(data) / len(data) if data else 0\n    results['summary'] = '共' + str(len(data)) + '条记录'\n    return results".format(topic.lower().replace(' ', '_'))
            }
        }

        fb = fallback_questions.get(q_type, fallback_questions["choice"])
        return {"id": idx, "type": q_type, "difficulty": level, "subject": subject_name, "topic": topic, **fb}


class CaseAgent(BaseGeneratorAgent):
    name = "case"
    description = "生成实操案例和项目练习"

    def generate(self, context: dict) -> dict:
        subject = context.get("subject", "computer_science")
        subject_name = context.get("subject_name", subject)
        level = context.get("level", 1)
        topic = context.get("topic", subject_name)

        level_names = {1: "入门", 2: "进阶", 3: "高级", 4: "专家"}
        level_name = level_names.get(level, "入门")

        return {
            "type": "case",
            "title": f"【{level_name}实战】{subject_name}·{topic}实操案例",
            "format": "markdown",
            "generated_at": datetime.utcnow().isoformat(),
            "case": self._build_case(subject_name, topic, level_name, level),
            "metadata": {
                "subject": subject,
                "level": level,
                "topic": topic,
                "difficulty": level_name,
                "estimated_time": f"{random.randint(1,4)}小时"
            }
        }

    def _build_case(self, subject, topic, level_name, level_id):
        """构建案例项目（LLM优先，失败回退）"""
        try:
            from utils import call_llm, call_llm_json
            sys_prompt = f"你是一个{subject}领域的实战项目导师，产出高质量案例。"
            user_prompt = (
                f"请为{subject}课程设计一个与{topic}相关的实战项目案例。\n"
                f"学生水平：{level_name}（Level {level_id}/4）。\n\n"
                "请包含：\n"
                "1. 案例标题（有具体场景）\n"
                "2. 项目背景（真实应用场景描述）\n"
                "3. 学习目标（2-3个具体目标）\n"
                "4. 功能需求（3-5条，逐条描述）\n"
                "5. 实现步骤（分步指导，每步含提示）\n"
                "6. 评估标准\n"
                f"难度适配{level_name}水平。\n"
                "只输出JSON：{{\"title\": \"案例标题\", \"background\": \"背景\", \"objectives\": [\"目标1\"], \"requirements\": [\"需求1\"], \"steps\": [{{\"step\": int, \"title\": \"步骤名\", \"content\": \"内容\", \"hint\": \"提示\"}}], \"evaluation_criteria\": [\"标准1\"]}}"
            )
            parsed = call_llm_json(sys_prompt, user_prompt, agent_name='CaseAgent')
            if parsed:
                parsed["generated_by"] = "llm"
                return parsed
        except Exception as e:
            print(f"[CaseAgent] LLM失败: {e}")

        # --- 增强的回退案例模板 ---
        return {
            "title": f"实战案例：基于{topic}的{subject}应用开发",
            "background": f"假设你是一家初创公司的技术负责人，需要开发一个基于{topic}的核心功能模块。"
                         f"你的团队规模小、时间紧，需要快速产出一个可演示的MVP（最小可行产品）。"
                         f"本案例将带你从需求分析到功能实现，完整走一遍{subject}项目的开发流程。",
            "objectives": [
                f"掌握{topic}在{subject}中的核心实现方法",
                f"独立完成一个从需求到实现的完整项目",
                f"学会调试和优化{topic}相关的常见问题"
            ],
            "requirements": [
                f"实现{topic}的基本功能：能够正确输入、处理、输出",
                "处理至少3种边界情况（空输入、异常值、大数量）",
                "添加基础错误处理和用户提示",
                "输出结果格式规范，便于后续集成",
                f"代码注释清晰，关键逻辑有说明{topic}文档标准"
            ],
            "steps": [
                {"step": 1, "title": "需求分析与设计",
                 "content": f"仔细阅读需求，画出{topic}功能模块的流程图。考虑输入是什么、经过什么处理、输出什么。",
                 "hint": "先在纸上画出流程图，明确每个步骤的输入输出"},
                {"step": 2, "title": "搭建项目骨架",
                 "content": "创建项目目录结构，编写主函数框架和核心数据模型。不急于实现细节，先搭好架子。",
                 "hint": "使用标准项目结构：src/ tests/ docs/ requirements.txt"},
                {"step": 3, "title": f"实现{topic}核心逻辑",
                 "content": f"按照流程图逐步实现核心功能。每实现一个子功能，立即运行测试验证。",
                 "hint": "从最简单的功能开始，逐步增加复杂度。测试驱动开发是最好的方式。"},
                {"step": 4, "title": "处理边界情况",
                 "content": "检查空输入、异常值、大数据量等情况。添加对应的保护逻辑和错误提示。",
                 "hint": "边界情况往往是最容易出bug的地方，不要跳过这一步"},
                {"step": 5, "title": "测试与优化",
                 "content": "编写测试用例覆盖核心功能和边界情况。分析性能瓶颈并优化。",
                 "hint": "优先保证功能正确，再考虑性能优化"}
            ],
            "evaluation_criteria": [
                "✅ 核心功能完整实现并能正确运行",
                "✅ 边界情况处理完善，无崩溃风险",
                "✅ 代码结构清晰，有适当注释",
                "✅ 有至少5个测试用例覆盖核心逻辑"
            ]
        }


class ResourceRecommenderAgent(BaseGeneratorAgent):
    """推荐相关视频教程、书籍和论文（原MultimediaAgent，已重命名以准确反映功能）"""
    name = "multimedia"
    description = "推荐视频教程、书籍和论文"

    # 学科映射 → 推荐资源库（按难度分级）
    RESOURCE_DB = {
        "ai": {
            "name": "人工智能/机器学习",
            "videos": [
                # level 1
                {"title": "吴恩达《机器学习》", "url": "https://www.coursera.org/learn/machine-learning", "platform": "Coursera", "duration": "~60h", "level": 1},
                {"title": "3Blue1Brown 神经网络可视化", "url": "https://www.bilibili.com/video/BV1bx411M7Zx", "platform": "B站", "duration": "~2h", "level": 1},
                {"title": "台大林轩田《机器学习基石》", "url": "https://www.bilibili.com/video/BV13W411P7Z4", "platform": "B站", "duration": "~40h", "level": 1},
                {"title": "李宏毅《机器学习》2023 入门", "url": "https://www.bilibili.com/video/BV1Wv411h7Uk", "platform": "B站", "duration": "~35h", "level": 1},
                {"title": "MIT 6.034 人工智能导论", "url": "https://ocw.mit.edu/courses/6-034-artificial-intelligence-fall-2010/", "platform": "MIT OCW", "duration": "~40h", "level": 1},
                {"title": "浙江大学《机器学习》Mooc", "url": "https://www.icourse163.org/course/ZJU-1002643002", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "Kaggle 入门机器学习", "url": "https://www.kaggle.com/learn/intro-to-machine-learning", "platform": "Kaggle Learn", "duration": "~4h", "level": 1},
                {"title": "AI入门：零基础学机器学习", "url": "https://www.bilibili.com/video/BV1ht4y1Y78R", "platform": "B站", "duration": "~20h", "level": 1},
                # level 2
                {"title": "李宏毅《深度学习》", "url": "https://speech.ee.ntu.edu.tw/~hylee/ml/2021-spring.html", "platform": "YouTube/B站", "duration": "~40h", "level": 2},
                {"title": "动手学深度学习(Li Mu)", "url": "https://space.bilibili.com/1567748478/channel/seriesdetail?sid=358497", "platform": "B站", "duration": "~50h", "level": 2},
                {"title": "Fast.ai 实用深度学习", "url": "https://course.fast.ai/", "platform": "fast.ai", "duration": "~30h", "level": 2},
                {"title": "MIT 6.S191 深度学习导论", "url": "http://introtodeeplearning.com/", "platform": "MIT OCW", "duration": "~15h", "level": 2},
                {"title": "台大林轩田《机器学习技术》", "url": "https://www.bilibili.com/video/BV1ix411N7dW", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "Hands-On ML with Scikit-Learn", "url": "https://www.youtube.com/playlist?list=PL5-da3qGB5IC5q_9rQx27eU6P-Yj_4Z1o", "platform": "YouTube", "duration": "~25h", "level": 2},
                {"title": "Stanford CS229 机器学习", "url": "https://see.stanford.edu/Course/CS229", "platform": "Stanford", "duration": "~60h", "level": 2},
                {"title": "Dive into Deep Learning (D2L.ai)", "url": "https://d2l.ai/", "platform": "d2l.ai", "duration": "自定进度", "level": 2},
                # level 3
                {"title": "Stanford CS231n 计算机视觉", "url": "https://www.bilibili.com/video/BV1nJ411z7fe", "platform": "B站", "duration": "~30h", "level": 3},
                {"title": "Stanford CS224n NLP与深度学习", "url": "https://www.bilibili.com/video/BV1pt411h7aT", "platform": "B站", "duration": "~35h", "level": 3},
                {"title": "UC Berkeley CS285 深度强化学习", "url": "https://www.bilibili.com/video/BV1gW411Z7Xy", "platform": "B站", "duration": "~35h", "level": 3},
                {"title": "Stanford CS230 深度学习进阶", "url": "https://cs230.stanford.edu/", "platform": "Stanford", "duration": "~40h", "level": 3},
                {"title": "CVPR 2024 前沿论文精讲", "url": "https://www.bilibili.com/video/BV1sV421f72w", "platform": "B站", "duration": "~15h", "level": 3},
                {"title": "NeurIPS 2023 论文导读", "url": "https://www.bilibili.com/video/BV1vK411L75u", "platform": "B站", "duration": "~10h", "level": 3},
                {"title": "OpenAI 最新进展系列", "url": "https://www.youtube.com/user/OpenAI/featured", "platform": "YouTube", "duration": "自定进度", "level": 3},
                {"title": "ICML 2024 前沿论文讲解", "url": "https://icml.cc/virtual/2024/index.html", "platform": "ICML", "duration": "自定进度", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《人工智能基础》", "author": "蔡自兴", "publisher": "清华大学出版社", "level": 1, "desc": "AI入门经典教材，覆盖各分支"},
                {"title": "《机器学习》（西瓜书）", "author": "周志华", "publisher": "清华大学出版社", "level": 2, "desc": "国内最经典的ML教材，理论扎实"},
                {"title": "《动手学深度学习》", "author": "Aston Zhang 等", "publisher": "人民邮电出版社", "level": 1, "desc": "代码理论结合，入门友好"},
                {"title": "《Python机器学习》", "author": "Sebastian Raschka", "publisher": "Packt", "level": 1, "desc": "实战导向，大量sklearn代码"},
                {"title": "《机器学习实战》", "author": "Peter Harrington", "publisher": "人民邮电出版社", "level": 1, "desc": "算法+Python代码，实战入门"},
                {"title": "《图解机器学习》", "author": "杉山将", "publisher": "人民邮电出版社", "level": 1, "desc": "图解决解，易读入门"},
                {"title": "《深入浅出数据挖掘》", "author": "范明", "publisher": "机械工业出版社", "level": 1, "desc": "机器学习与数据挖掘基础"},
                # level 2
                {"title": "《统计学习方法》", "author": "李航", "publisher": "清华大学出版社", "level": 2, "desc": "算法推导清晰，适合打好理论基础"},
                {"title": "《机器学习实战：基于Scikit-Learn与TensorFlow》", "author": "Aurélien Géron", "publisher": "机械工业出版社", "level": 2, "desc": "ML圣经，全栈实战"},
                {"title": "《模式识别与机器学习》(PRML简版)", "author": "Christopher Bishop", "publisher": "Springer", "level": 2, "desc": "贝叶斯视角机器学习"},
                {"title": "《神经网络与深度学习》", "author": "邱锡鹏", "publisher": "机械工业出版社", "level": 2, "desc": "复旦教材，原理清晰"},
                {"title": "《机器学习：贝叶斯与统计视角》", "author": "Murphy", "publisher": "MIT Press", "level": 2, "desc": "概率机器学习经典"},
                {"title": "《支持向量机：理论与算法》", "author": "邓乃扬", "publisher": "科学出版社", "level": 2, "desc": "SVM专题深入"},
                # level 3
                {"title": "《深度学习》（花书）", "author": "Ian Goodfellow", "publisher": "MIT Press", "level": 3, "desc": "深度学习圣经，适合进阶"},
                {"title": "PRML", "author": "Christopher Bishop", "publisher": "Springer", "level": 3, "desc": "贝叶斯学派经典，数学要求高"},
                {"title": "《模式识别》（模式分类）", "author": "Duda & Hart", "publisher": "Wiley", "level": 3, "desc": "经典模式识别教材"},
                {"title": "《深度学习进阶：优化与正则》", "author": "Ian Goodfellow 等", "publisher": "MIT Press", "level": 3, "desc": "深度学习调优方法"},
                {"title": "《概率图模型：原理与技术》", "author": "Koller & Friedman", "publisher": "MIT Press", "level": 3, "desc": "PGM权威参考"},
                {"title": "《强化学习：导论》", "author": "Sutton & Barto", "publisher": "MIT Press", "level": 3, "desc": "RL领域圣经"},
            ],
            "papers": [
                # level 1 - 经典里程碑 (必读)
                {"title": "Attention Is All You Need", "authors": "Vaswani et al.", "year": 2017, "venue": "NeurIPS", "level": 2, "desc": "Transformer开山之作，GPT/LLM基础"},
                {"title": "ImageNet Classification with Deep CNNs", "authors": "Alex Krizhevsky et al.", "year": 2012, "venue": "NeurIPS", "level": 2, "desc": "AlexNet，深度学习里程碑"},
                {"title": "Gradient-Based Learning Applied to Doc Recognition", "authors": "LeCun et al.", "year": 1998, "venue": "Proc. IEEE", "level": 1, "desc": "LeNet-5，CNN开山之作"},
                {"title": "The Elements of Statistical Learning", "authors": "Hastie et al.", "year": 2009, "venue": "Springer", "level": 2, "desc": "统计学习经典参考书"},
                # level 2 - 重要方法论文
                {"title": "Deep Residual Learning for Image Recognition", "authors": "He et al.", "year": 2016, "venue": "CVPR", "level": 3, "desc": "ResNet残差网络，解决深层退化"},
                {"title": "BERT: Pre-training of Deep Bidirectional Transformers", "authors": "Devlin et al.", "year": 2019, "venue": "NAACL", "level": 2, "desc": "NLP预训练模型里程碑"},
                {"title": "Generative Adversarial Networks", "authors": "Ian Goodfellow et al.", "year": 2014, "venue": "NeurIPS", "level": 2, "desc": "GAN经典论文，生成式AI奠基"},
                {"title": "Distributed Representations of Words and Phrases", "authors": "Mikolov et al.", "year": 2013, "venue": "NeurIPS", "level": 2, "desc": "Word2Vec词向量"},
                {"title": "Random Forests", "authors": "Leo Breiman", "year": 2001, "venue": "Machine Learning", "level": 1, "desc": "随机森林经典"},
                {"title": "Support-Vector Networks", "authors": "Cortes & Vapnik", "year": 1995, "venue": "Machine Learning", "level": 2, "desc": "SVM原始论文"},
                {"title": "Dropout: A Simple Way to Prevent NN Overfitting", "authors": "Hinton et al.", "year": 2014, "venue": "JMLR", "level": 1, "desc": "Dropout正则化方法"},
                {"title": "Adam: A Method for Stochastic Optimization", "authors": "Kingma & Ba", "year": 2015, "venue": "ICLR", "level": 1, "desc": "Adam优化器，最常用优化器"},
                {"title": "Language Models are Few-Shot Learners", "authors": "Brown et al.", "year": 2020, "venue": "NeurIPS", "level": 2, "desc": "GPT-3，大模型里程碑"},
                {"title": "LLaMA: Open and Efficient Foundation Language Models", "authors": "Touvron et al.", "year": 2023, "venue": "ArXiv", "level": 2, "desc": "LLaMA开源大模型系列"},
                # level 3 - 深度前沿论文
                {"title": "Scaling Laws for Neural Language Models", "authors": "Kaplan et al.", "year": 2020, "venue": "ArXiv", "level": 3, "desc": "大模型规模定律，重要理论"},
                {"title": "Training Compute-Optimal Large Language Models", "authors": "Hoffmann et al.", "year": 2022, "venue": "ArXiv", "level": 3, "desc": "Chinchilla尺度法则"},
                {"title": "Diffusion Models Beat GANs on Image Synthesis", "authors": "Dhariwal & Nichol", "year": 2021, "venue": "NeurIPS", "level": 3, "desc": "扩散模型超越GAN"},
                {"title": "High-Resolution Image Synthesis with Latent Diffusion", "authors": "Rombach et al.", "year": 2022, "venue": "CVPR", "level": 3, "desc": "Stable Diffusion核心论文"},
            ]
        },
        "python": {
            "name": "Python编程",
            "videos": [
                # level 1
                {"title": "Python官方教程", "url": "https://docs.python.org/3/tutorial/", "platform": "Python.org", "duration": "自定进度", "level": 1},
                {"title": "CS50P Python入门", "url": "https://cs50.harvard.edu/python/", "platform": "Harvard", "duration": "~30h", "level": 1},
                {"title": "Corey Schafer Python教程", "url": "https://www.youtube.com/user/schafer5", "platform": "YouTube", "duration": "~20h", "level": 1},
                {"title": "小甲鱼零基础学Python", "url": "https://www.bilibili.com/video/BV1c4411e77t", "platform": "B站", "duration": "~50h", "level": 1},
                {"title": "黑马程序员Python入门", "url": "https://www.bilibili.com/video/BV1wD4y1o7AS", "platform": "B站", "duration": "~60h", "level": 1},
                {"title": "廖雪峰Python教程", "url": "https://www.liaoxuefeng.com/wiki/1016959663602400", "platform": "廖雪峰官网", "duration": "自定进度", "level": 1},
                {"title": "Coursera Python for Everybody", "url": "https://www.coursera.org/specializations/python", "platform": "Coursera", "duration": "~40h", "level": 1},
                {"title": "SoloLearn Python入门", "url": "https://www.sololearn.com/Course/Python/", "platform": "SoloLearn", "duration": "自定进度", "level": 1},
                # level 2
                {"title": "Fluent Python实战", "url": "https://www.bilibili.com/video/BV1Q5411u7rL", "platform": "B站", "duration": "~15h", "level": 2},
                {"title": "Python高级编程", "url": "https://www.bilibili.com/video/BV1tZ4y1L7rX", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "MIT 6.0001 CS Python导论", "url": "https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/", "platform": "MIT OCW", "duration": "~40h", "level": 2},
                {"title": "Python设计模式", "url": "https://www.bilibili.com/video/BV1Yf4y1n76m", "platform": "B站", "duration": "~15h", "level": 2},
                {"title": "Python并发编程", "url": "https://www.bilibili.com/video/BV1bK411A7tV", "platform": "B站", "duration": "~20h", "level": 2},
                {"title": "Real Python 中级系列", "url": "https://realpython.com/", "platform": "Real Python", "duration": "自定进度", "level": 2},
                {"title": "Python网络编程", "url": "https://www.bilibili.com/video/BV1pt4y1w7P7", "platform": "B站", "duration": "~15h", "level": 2},
                {"title": "Python单元测试(pytest)", "url": "https://www.youtube.com/playlist?list=PL-osiE80TeTskwr5JyQKUkh2PkqPuZ4hd", "platform": "YouTube", "duration": "~8h", "level": 2},
                # level 3
                {"title": "Fluent Python 第二版 精读", "url": "https://www.oreilly.com/library/view/fluent-python-2nd/9781492056348/", "platform": "O'Reilly", "duration": "自定进度", "level": 3},
                {"title": "Python源码剖析(CPython)", "url": "https://www.bilibili.com/video/BV1mD4y1s77s", "platform": "B站", "duration": "~40h", "level": 3},
                {"title": "Python性能优化", "url": "https://www.youtube.com/playlist?list=PLRqwX-V7Uu6bXUJvjnMWWU46T2kPUV9mH", "platform": "YouTube", "duration": "~10h", "level": 3},
                {"title": "CPython 内核开发", "url": "https://realpython.com/cpython-source-code-guide/", "platform": "Real Python", "duration": "自定进度", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《Python编程：从入门到实践》", "author": "Eric Matthes", "publisher": "人民邮电出版社", "level": 1, "desc": "最适合零基础的Python书，项目实战多"},
                {"title": "《Python基础教程》", "author": "Magnus Hetland", "publisher": "人民邮电出版社", "level": 1, "desc": "经典入门教材，循序渐进"},
                {"title": "《笨办法学Python》", "author": "Zed Shaw", "publisher": "人民邮电出版社", "level": 1, "desc": "练习驱动，边做边学"},
                {"title": "《Python Cookbook 中文版》(入门)", "author": "David Beazley", "publisher": "人民邮电出版社", "level": 1, "desc": "常见编程任务食谱"},
                {"title": "《Python编程快速上手》", "author": "Al Sweigart", "publisher": "人民邮电出版社", "level": 1, "desc": "自动化办公，实用入门"},
                {"title": "《看漫画学Python》", "author": "关东升", "publisher": "清华大学出版社", "level": 1, "desc": "图解入门，轻松有趣"},
                # level 2
                {"title": "《流畅的Python》", "author": "Luciano Ramalho", "publisher": "O Reilly", "level": 2, "desc": "进阶必备，深入Python特性"},
                {"title": "《Python Cookbook》(第三版)", "author": "David Beazley", "publisher": "O Reilly", "level": 3, "desc": "Python高阶技巧集，问题+方案"},
                {"title": "《Effective Python》", "author": "Brett Slatkin", "publisher": "Pearson", "level": 2, "desc": "编写高质量Python的90个建议"},
                {"title": "《Python高手之路》", "author": "朱卫军", "publisher": "人民邮电出版社", "level": 2, "desc": "从初级到高级工程师"},
                {"title": "《Python数据结构与算法》", "author": "Bradley Miller", "publisher": "机械工业出版社", "level": 2, "desc": "Python实现经典DSA"},
                {"title": "《Python核心编程》", "author": "Wesley Chun", "publisher": "人民邮电出版社", "level": 2, "desc": "全面深入讲解Python核心"},
                # level 3
                {"title": "《Python Cookbook》(第三版高阶)", "author": "David Beazley", "publisher": "O Reilly", "level": 3, "desc": "Python高阶技巧集"},
                {"title": "《Python源码剖析》", "author": "陈儒", "publisher": "电子工业出版社", "level": 3, "desc": "深入CPython解释器内部"},
                {"title": "《CPython Internals》", "author": "Anthony Shaw", "publisher": "Real Python", "level": 3, "desc": "Python 3.9+内核解读"},
                {"title": "《高级Python编程》", "author": "Dr. Gabriele Lanaro", "publisher": "Packt", "level": 3, "desc": "性能优化并发高级特性"},
            ],
            "papers": [
                {"title": "PEP 8 - Python Style Guide", "authors": "Guido van Rossum et al.", "year": 2001, "venue": "Python.org", "level": 1, "desc": "Python编码规范必读"},
                {"title": "PEP 20 - The Zen of Python", "authors": "Tim Peters", "year": 2004, "venue": "Python.org", "level": 1, "desc": "Python设计哲学"},
                {"title": "Python for Beginners (Official Tutorial)", "authors": "Python Software Foundation", "year": 2001, "venue": "Python.org", "level": 1, "desc": "Python官方入门教程推荐文"},
                {"title": "Automate the Boring Stuff", "authors": "Al Sweigart", "year": 2015, "venue": "No Starch", "level": 1, "desc": "Python编程实践入门推荐"},
                {"title": "PEP 484 Type Hints", "authors": "Guido et al.", "year": 2014, "venue": "Python.org", "level": 2, "desc": "Python类型提示规范"},
                {"title": "Python's Design Philosophy", "authors": "Guido van Rossum", "year": 2000, "venue": "ICLP", "level": 2, "desc": "Python设计思想"},
                {"title": "Why Python is Slow (Looking Inside)", "authors": "Jake VanderPlas", "year": 2014, "venue": "ArXiv", "level": 3, "desc": "Python性能分析"},
                {"title": "The Python GIL: A Clear Picture", "authors": "David Beazley", "year": 2010, "venue": "PyCon", "level": 3, "desc": "Python GIL机制详解"},
            ]
        },
        "web": {
            "name": "Web开发",
            "videos": [
                # level 1
                {"title": "The Odin Project", "url": "https://www.theodinproject.com/", "platform": "Odin", "duration": "~100h", "level": 1},
                {"title": "尚硅谷全栈教程", "url": "https://www.bilibili.com/video/BV1Bb411d7SL", "platform": "B站", "duration": "~60h", "level": 1},
                {"title": "MDN Web Docs 学习路径", "url": "https://developer.mozilla.org/zh-CN/docs/Learn", "platform": "MDN", "duration": "自定进度", "level": 1},
                {"title": "黑马程序员前端入门", "url": "https://www.bilibili.com/video/BV14J4114768", "platform": "B站", "duration": "~80h", "level": 1},
                {"title": "freeCodeCamp 全栈教程", "url": "https://www.freecodecamp.org/", "platform": "freeCodeCamp", "duration": "自定进度", "level": 1},
                {"title": "W3C Web入门教程", "url": "https://www.w3schools.com/", "platform": "W3Schools", "duration": "自定进度", "level": 1},
                {"title": "HTML/CSS零基础", "url": "https://www.bilibili.com/video/BV1XJ411X7Ud", "platform": "B站", "duration": "~30h", "level": 1},
                {"title": "CodeWithHarry 前端入门", "url": "https://www.youtube.com/playlist?list=PLu0W_9lII9agiCUZYRsvtGTXdxkzPyItg", "platform": "YouTube", "duration": "~30h", "level": 1},
                # level 2
                {"title": "Full Stack Open", "url": "https://fullstackopen.com/", "platform": "赫尔辛基大学", "duration": "~80h", "level": 2},
                {"title": "Vue3 + TypeScript 实战", "url": "https://www.bilibili.com/video/BV1Zy4y1K7SH", "platform": "B站", "duration": "~40h", "level": 2},
                {"title": "React 官方教程进阶", "url": "https://react.dev/learn", "platform": "React.dev", "duration": "自定进度", "level": 2},
                {"title": "Next.js 13 全栈开发", "url": "https://www.bilibili.com/video/BV1T84y1n7E2", "platform": "B站", "duration": "~20h", "level": 2},
                {"title": "Node.js 实战全栈", "url": "https://www.bilibili.com/video/BV1Ns411N76q", "platform": "B站", "duration": "~40h", "level": 2},
                {"title": "Flask Web实战开发", "url": "https://www.bilibili.com/video/BV17r4y1y7jJ", "platform": "B站", "duration": "~25h", "level": 2},
                {"title": "Django 实战开发", "url": "https://www.bilibili.com/video/BV1NJ411J79W", "platform": "B站", "duration": "~35h", "level": 2},
                {"title": "Webpack/Vite 前端工程化", "url": "https://www.bilibili.com/video/BV1Vf4y1T7bw", "platform": "B站", "duration": "~20h", "level": 2},
                # level 3
                {"title": "CS50 Web Programming with Python & JS", "url": "https://cs50.harvard.edu/web/", "platform": "Harvard", "duration": "~60h", "level": 3},
                {"title": "前端性能优化实战", "url": "https://www.bilibili.com/video/BV1X5411G7u3", "platform": "B站", "duration": "~15h", "level": 3},
                {"title": "系统设计面试", "url": "https://www.youtube.com/c/SystemDesignInterview", "platform": "YouTube", "duration": "自定进度", "level": 3},
                {"title": "Kubernetes 微服务部署", "url": "https://www.youtube.com/playlist?list=PLy7NrYWoggjwP_LU1jYKw1GdP_LrZJ0nS", "platform": "YouTube", "duration": "~20h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《HTML与CSS：设计与构建网站》", "author": "Jon Duckett", "publisher": "Wiley", "level": 1, "desc": "图文并茂，入门友好"},
                {"title": "《JavaScript高级程序设计》(红宝书)", "author": "Nicholas Zakas", "publisher": "人民邮电出版社", "level": 2, "desc": "JS经典必读，前端圣经"},
                {"title": "《CSS权威指南》", "author": "Eric Meyer", "publisher": "O Reilly", "level": 1, "desc": "CSS全面讲解"},
                {"title": "《Head First HTML与CSS》", "author": "Eric Freeman", "publisher": "中国电力出版社", "level": 1, "desc": "轻松入门Web"},
                {"title": "《图解HTTP》", "author": "上野宣", "publisher": "人民邮电出版社", "level": 1, "desc": "HTTP协议图解入门"},
                {"title": "《响应式Web设计》", "author": "Ethan Marcotte", "publisher": "人民邮电出版社", "level": 1, "desc": "响应式设计基础"},
                # level 2
                {"title": "《深入浅出Node.js》", "author": "朴灵", "publisher": "人民邮电出版社", "level": 2, "desc": "Node.js原理与实践"},
                {"title": "《ES6标准入门》", "author": "阮一峰", "publisher": "电子工业出版社", "level": 2, "desc": "JavaScript ES6+权威"},
                {"title": "《你不知道的JavaScript》上/中/下", "author": "Kyle Simpson", "publisher": "人民邮电出版社", "level": 2, "desc": "深入理解JS原理"},
                {"title": "《Vue.js设计与实现》", "author": "霍春阳", "publisher": "人民邮电出版社", "level": 2, "desc": "Vue3源码级解读"},
                {"title": "《React设计原理》", "author": "卡颂", "publisher": "电子工业出版社", "level": 2, "desc": "React Fiber架构详解"},
                {"title": "《Web安全深度剖析》", "author": "张炳帅", "publisher": "电子工业出版社", "level": 2, "desc": "Web安全攻防实战"},
                # level 3
                {"title": "《代码整洁之道》(Web版)", "author": "Robert Martin", "publisher": "Prentice Hall", "level": 3, "desc": "高质量代码编写"},
                {"title": "《高性能网站建设指南》", "author": "Steve Souders", "publisher": "O Reilly", "level": 3, "desc": "前端性能优化圣经"},
                {"title": "《Web性能实战》", "author": "Jeremy Wagner", "publisher": "Manning", "level": 3, "desc": "性能优化实操指南"},
                {"title": "《微服务架构设计模式》", "author": "Chris Richardson", "publisher": "机械工业出版社", "level": 3, "desc": "微服务架构经典"},
            ],
            "papers": [
                {"title": "The Node.js Event Loop Explained", "authors": "Node.js Foundation", "year": 2018, "venue": "Node.js Docs", "level": 2, "desc": "事件循环机制详解"},
                {"title": "REST Architectural Style", "authors": "Roy Fielding", "year": 2000, "venue": "UC Irvine", "level": 2, "desc": "REST API架构奠基"},
                {"title": "Ajax: A New Approach to Web Apps", "authors": "Jesse Garrett", "year": 2005, "venue": "Adaptive Path", "level": 1, "desc": "Ajax概念起源入门"},
                {"title": "Progressive Web Apps", "authors": "Google Devs", "year": 2015, "venue": "Google I/O", "level": 2, "desc": "PWA技术介绍"},
                {"title": "A Quick Introduction to WebAssembly", "authors": "Andreas Rossberg", "year": 2018, "venue": "Google", "level": 3, "desc": "WASM标准介绍"},
                {"title": "GraphQL: A Data Query Language", "authors": "Facebook", "year": 2016, "venue": "GraphQL.org", "level": 3, "desc": "GraphQL数据查询语言"},
                {"title": "MDN Getting Started with the Web", "authors": "Mozilla Contributors", "year": 2005, "venue": "MDN", "level": 1, "desc": "MDN Web入门指南推荐"},
                {"title": "Eloquent JavaScript (Haverbeke)", "authors": "Marijn Haverbeke", "year": 2007, "venue": "No Starch", "level": 1, "desc": "JS编程入门推荐，Web前端必读"},
                {"title": "Web Development with Node & Express", "authors": "Ethan Brown", "year": 2014, "venue": "O'Reilly", "level": 1, "desc": "Node.js后端开发入门推荐"},
            ]
        },
        "data_science": {
            "name": "数据科学",
            "videos": [
                # level 1
                {"title": "Kaggle Learn", "url": "https://www.kaggle.com/learn", "platform": "Kaggle", "duration": "自定进度", "level": 1},
                {"title": "Joel Grus 数据科学", "url": "https://www.youtube.com/playlist?list=PL5-da3qGB5ICeVaQuyd56fiM1RZ6vDpgX", "platform": "YouTube", "duration": "~15h", "level": 1},
                {"title": "Udemy Data Science A-Z", "url": "https://www.udemy.com/course/datascience/", "platform": "Udemy", "duration": "~40h", "level": 1},
                {"title": "可汗学院 统计学", "url": "https://www.khanacademy.org/math/statistics-probability", "platform": "Khan Academy", "duration": "自定进度", "level": 1},
                {"title": "Python数据分析入门", "url": "https://www.bilibili.com/video/BV1hE411t7RN", "platform": "B站", "duration": "~30h", "level": 1},
                {"title": "数据分析Excel+SQL", "url": "https://www.bilibili.com/video/BV1eT411c7w9", "platform": "B站", "duration": "~20h", "level": 1},
                {"title": "Coursera IBM Data Science", "url": "https://www.coursera.org/professional-certificates/ibm-data-science", "platform": "Coursera", "duration": "~80h", "level": 1},
                {"title": "Harvard PH125x Data Science", "url": "https://www.edx.org/professional-certificate/harvardx-data-science", "platform": "edX", "duration": "~80h", "level": 1},
                # level 2
                {"title": "Stanford Statistics 110 概率论", "url": "https://projects.iq.harvard.edu/stat110/youtube", "platform": "Harvard", "duration": "~40h", "level": 2},
                {"title": "MIT 18.650 统计学应用", "url": "https://ocw.mit.edu/courses/18-650-statistics-for-applications-fall-2016/", "platform": "MIT OCW", "duration": "~35h", "level": 2},
                {"title": "SQL 50题实战", "url": "https://www.bilibili.com/video/BV1XA411a7tZ", "platform": "B站", "duration": "~10h", "level": 2},
                {"title": "数据可视化（Plotly/D3）", "url": "https://www.bilibili.com/video/BV1t4411A75u", "platform": "B站", "duration": "~15h", "level": 2},
                {"title": "JHU Data Science 专项", "url": "https://www.coursera.org/specializations/jhu-data-science", "platform": "Coursera", "duration": "~100h", "level": 2},
                {"title": "Datacamp Python数据科学家", "url": "https://www.datacamp.com/tracks/data-scientist-with-python", "platform": "DataCamp", "duration": "自定进度", "level": 2},
                {"title": "Hadoop/Spark 大数据", "url": "https://www.bilibili.com/video/BV1Nw411A7zV", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "统计学习(Stat Learning) Stanford", "url": "https://www.dataschool.io/15-hours-of-expert-machine-learning-videos/", "platform": "Stanford", "duration": "~15h", "level": 2},
                # level 3
                {"title": "Stanford STATS 202 机器学习", "url": "https://online.stanford.edu/courses/soe-ystats202-machine-learning-data-mining", "platform": "Stanford", "duration": "~40h", "level": 3},
                {"title": "因果推断与数据科学", "url": "https://www.bilibili.com/video/BV1qK411u7hF", "platform": "B站", "duration": "~20h", "level": 3},
                {"title": "深度学习与NLP 实战", "url": "https://www.bilibili.com/video/BV1KZ4y1h7aR", "platform": "B站", "duration": "~25h", "level": 3},
                {"title": "MLOps 机器学习工程化", "url": "https://www.youtube.com/playlist?list=PL3N9IuMTr3F_4vLwOZtD_1QqPpFk6mU0l", "platform": "YouTube", "duration": "~15h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《利用Python进行数据分析》", "author": "Wes McKinney", "publisher": "O Reilly", "level": 1, "desc": "pandas作者亲著，数据处理权威"},
                {"title": "《深入浅出统计学》", "author": "Dawn Griffiths", "publisher": "中国电力出版社", "level": 1, "desc": "Head First系列，轻松学统计"},
                {"title": "《赤裸裸的统计学》", "author": "Charles Wheelan", "publisher": "中信出版社", "level": 1, "desc": "统计学趣味入门"},
                {"title": "《SQL必知必会》", "author": "Ben Forta", "publisher": "人民邮电出版社", "level": 1, "desc": "SQL快速入门"},
                {"title": "《数据可视化实战》", "author": "Nathan Yau", "publisher": "人民邮电出版社", "level": 1, "desc": "R/Python数据可视化"},
                {"title": "《商务与经济统计》", "author": "Anderson", "publisher": "Cengage", "level": 1, "desc": "经典商务统计学"},
                # level 2
                {"title": "《Python数据科学手册》", "author": "Jake VanderPlas", "publisher": "O Reilly", "level": 2, "desc": "数据科学生态全览(NumPy/Pandas/Matplotlib/Scikit)"},
                {"title": "《统计学习导论》(ISL)", "author": "Gareth James", "publisher": "Springer", "level": 2, "desc": "斯坦福入门统计学习，带R/Python代码"},
                {"title": "《机器学习实战：基于Scikit-Learn、Keras与TensorFlow》", "author": "Aurélien Géron", "publisher": "机械工业出版社", "level": 2, "desc": "全栈数据科学圣经"},
                {"title": "《R语言实战》", "author": "Robert Kabacoff", "publisher": "人民邮电出版社", "level": 2, "desc": "R数据分析全面指南"},
                {"title": "《贝叶斯思维》", "author": "Allen Downey", "publisher": "人民邮电出版社", "level": 2, "desc": "贝叶斯统计Python实战"},
                {"title": "《特征工程入门与实践》", "author": "Sinan Ozdemir", "publisher": "人民邮电出版社", "level": 2, "desc": "FE特征工程实战"},
                # level 3
                {"title": "《The Elements of Statistical Learning》(ESL)", "author": "Hastie/Tibshirani/Friedman", "publisher": "Springer", "level": 3, "desc": "统计学习圣经，数学要求高"},
                {"title": "Scikit-learn: Machine Learning in Python", "authors": "Pedregosa et al.", "year": 2011, "venue": "JMLR", "level": 1, "desc": "sklearn框架论文"},
                {"title": "Stripe Data Science 实战指南", "authors": "Various", "year": 2023, "venue": "Stripe", "level": 3, "desc": "工业界数据科学实战"},
                {"title": "《Designing Data-Intensive Applications》(DDIA)", "author": "Martin Kleppmann", "publisher": "O Reilly", "level": 3, "desc": "大数据密集型应用架构经典"},
            ],
            "papers": [
                {"title": "Scikit-learn: Machine Learning in Python", "authors": "Pedregosa et al.", "year": 2011, "venue": "JMLR", "level": 1, "desc": "sklearn框架论文"},
                {"title": "pandas: Foundational Python Data Analysis Lib", "authors": "Wes McKinney", "year": 2010, "venue": "SciPy", "level": 1, "desc": "pandas框架介绍"},
                {"title": "Matplotlib: A 2D Graphics Environment", "authors": "John Hunter", "year": 2007, "venue": "CSE", "level": 1, "desc": "Matplotlib可视化框架"},
                {"title": "TensorFlow: Large-Scale ML on Heterogeneous Systems", "authors": "Dean et al.", "year": 2015, "venue": "OSDI", "level": 2, "desc": "TensorFlow框架论文"},
                {"title": "Apache Spark: Unified Engine for Big Data Processing", "authors": "Zaharia et al.", "year": 2016, "venue": "CACM", "level": 2, "desc": "Spark大数据框架"},
                {"title": "D3: Data-Driven Documents", "authors": "Bostock et al.", "year": 2011, "venue": "InfoVis", "level": 2, "desc": "D3.js数据可视化框架"},
                {"title": "MapReduce: Simplified Data Processing", "authors": "Dean & Ghemawat", "year": 2004, "venue": "OSDI", "level": 3, "desc": "分布式计算框架原型"},
                {"title": "The Google File System", "authors": "Ghemawat et al.", "year": 2003, "venue": "SOSP", "level": 3, "desc": "分布式文件系统经典"},
            ]
        },
        "computer_science": {
            "name": "计算机科学",
            "videos": [
                # level 1
                {"title": "CS50: 计算机科学导论", "url": "https://cs50.harvard.edu/", "platform": "Harvard/edX", "duration": "~60h", "level": 1},
                {"title": "数据结构与算法(浙大)", "url": "https://www.icourse163.org/course/ZJU-93001", "platform": "中国大学MOOC", "duration": "~40h", "level": 1},
                {"title": "Crash Course 计算机科学", "url": "https://www.bilibili.com/video/BV1EW411u7th", "platform": "B站", "duration": "~15h", "level": 1},
                {"title": "MIT 6.00 计算机科学导论", "url": "https://ocw.mit.edu/courses/6-00sc-introduction-to-computer-science-and-programming-spring-2011/", "platform": "MIT OCW", "duration": "~40h", "level": 1},
                {"title": "计算机组成原理", "url": "https://www.bilibili.com/video/BV1d5411m7i5", "platform": "B站", "duration": "~40h", "level": 1},
                {"title": "C语言程序设计", "url": "https://www.bilibili.com/video/BV1Nq4y1K7Uf", "platform": "B站", "duration": "~50h", "level": 1},
                {"title": "离散数学", "url": "https://www.bilibili.com/video/BV1NJ411t7dD", "platform": "B站", "duration": "~30h", "level": 1},
                {"title": "斯坦福CS101 计算机入门", "url": "https://web.stanford.edu/class/cs101/", "platform": "Stanford", "duration": "~30h", "level": 1},
                # level 2
                {"title": "操作系统(南京大学)", "url": "https://www.icourse163.org/course/NJU-1001625001", "platform": "中国大学MOOC", "duration": "~40h", "level": 2},
                {"title": "计算机网络：自顶向下方法", "url": "https://www.bilibili.com/video/BV1JV411t7ow", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "MIT 6.006 算法导论", "url": "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", "platform": "MIT OCW", "duration": "~50h", "level": 2},
                {"title": "编译原理(哈工大)", "url": "https://www.bilibili.com/video/BV1zW411t7YE", "platform": "B站", "duration": "~60h", "level": 2},
                {"title": "数据库系统概论(人大)", "url": "https://www.bilibili.com/video/BV1pW411W7Zi", "platform": "B站", "duration": "~45h", "level": 2},
                {"title": "MIT 6.033 计算机系统", "url": "https://ocw.mit.edu/courses/6-033-computer-system-engineering-spring-2018/", "platform": "MIT OCW", "duration": "~50h", "level": 2},
                {"title": "LeetCode 算法刷题精讲", "url": "https://www.bilibili.com/video/BV1nY4y1c7rP", "platform": "B站", "duration": "~50h", "level": 2},
                {"title": "Stanford CS143 编译器", "url": "https://web.stanford.edu/class/cs143/", "platform": "Stanford", "duration": "~40h", "level": 2},
                # level 3
                {"title": "MIT 6.046J 算法设计与分析", "url": "https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/", "platform": "MIT OCW", "duration": "~50h", "level": 3},
                {"title": "Stanford CS224W 图神经网络", "url": "https://www.bilibili.com/video/BV1pz4y1Z7tN", "platform": "B站", "duration": "~25h", "level": 3},
                {"title": "MIT 6.828 操作系统工程", "url": "https://ocw.mit.edu/courses/6-828-operating-system-engineering-fall-2012/", "platform": "MIT OCW", "duration": "~60h", "level": 3},
                {"title": "CMU 15-445 数据库系统", "url": "https://www.youtube.com/playlist?list=PLSE8ODhjZXjaKScG3l083oui0wnU4eQ5P", "platform": "CMU", "duration": "~40h", "level": 3},
                {"title": "MIT 6.824 分布式系统", "url": "https://ocw.mit.edu/courses/6-824-distributed-computer-systems-engineering-spring-2020/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "Stanford CS213 程序设计语言", "url": "https://www.youtube.com/playlist?list=PLpsqfE0b2dCq7G9T2F5C4l7Q8cL0eFh5o", "platform": "Stanford", "duration": "~30h", "level": 3},
                {"title": "Berkeley CS162 操作系统", "url": "https://www.bilibili.com/video/BV15Z4y1c7Hk", "platform": "B站", "duration": "~50h", "level": 3},
                {"title": "CMU CSAPP深入理解计算机系统", "url": "https://scs.hosted.panopto.com/Panopto/Pages/Sessions/List.aspx#folderID=%229a1b3bb1-bb97-436c-b3f6-a9a9554d2172%22", "platform": "CMU", "duration": "~45h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《深入理解计算机系统》(CSAPP)", "author": "Randal Bryant", "publisher": "机械工业出版社", "level": 2, "desc": "CS经典，硬件软件贯通"},
                {"title": "《计算机科学导论》", "author": "Behrouz Forouzan", "publisher": "机械工业出版社", "level": 1, "desc": "CS全景入门"},
                {"title": "《C程序设计语言》(K&R)", "author": "Kernighan & Ritchie", "publisher": "Prentice Hall", "level": 1, "desc": "C语言圣经"},
                {"title": "《数据结构》(严蔚敏)", "author": "严蔚敏", "publisher": "清华大学出版社", "level": 1, "desc": "国内经典DS教材"},
                {"title": "《离散数学》(左孝凌)", "author": "左孝凌", "publisher": "上海科技文献", "level": 1, "desc": "CS数学基础"},
                {"title": "《编码：隐匿在计算机软硬件背后的语言》", "author": "Charles Petzold", "publisher": "电子工业出版社", "level": 1, "desc": "计算机原理图解入门"},
                # level 2
                {"title": "《算法导论》(CLRS)", "author": "Cormen et al.", "publisher": "MIT Press", "level": 3, "desc": "算法圣经"},
                {"title": "《计算机网络：自顶向下方法》", "author": "James Kurose", "publisher": "机械工业出版社", "level": 1, "desc": "网络入门经典"},
                {"title": "《操作系统概念》(恐龙书)", "author": "Silberschatz", "publisher": "Wiley", "level": 2, "desc": "操作系统标准教材"},
                {"title": "《数据库系统概念》", "author": "Abraham Silberschatz", "publisher": "机械工业出版社", "level": 2, "desc": "数据库经典"},
                {"title": "《编译原理》(龙书)", "author": "Aho et al.", "publisher": "Pearson", "level": 3, "desc": "编译原理权威"},
                {"title": "《算法设计与分析基础》", "author": "Anany Levitin", "publisher": "清华大学出版社", "level": 2, "desc": "算法设计方法论"},
                # level 3
                {"title": "《算法导论》(CLRS)", "author": "Cormen et al.", "publisher": "MIT Press", "level": 3, "desc": "算法圣经，进阶必备"},
                {"title": "《计算机程序的构造和解释》(SICP)", "author": "Abelson & Sussman", "publisher": "MIT Press", "level": 3, "desc": "编程思想经典"},
                {"title": "《龙书编译原理》", "author": "Aho Sethi Ullman", "publisher": "Pearson", "level": 3, "desc": "编译器设计权威"},
                {"title": "《分布式系统概念与设计》", "author": "George Coulouris", "publisher": "Pearson", "level": 3, "desc": "分布式系统经典"},
                {"title": "《数据库系统实现》", "author": "Garcia-Molina", "publisher": "机械工业出版社", "level": 3, "desc": "DB内部实现详解"},
                {"title": "《TAOCP》(计算机程序设计艺术)", "author": "Donald Knuth", "publisher": "Addison-Wesley", "level": 3, "desc": "算法领域终极巨著"},
            ],
            "papers": [
                # level 1 - 必读CS经典
                {"title": "The Google File System", "authors": "Ghemawat et al.", "year": 2003, "venue": "SOSP", "level": 3, "desc": "分布式文件系统经典"},
                {"title": "MapReduce: Simplified Data Processing", "authors": "Dean & Ghemawat", "year": 2004, "venue": "OSDI", "level": 3, "desc": "分布式计算框架原型"},
                {"title": "A Mathematical Theory of Communication", "authors": "Claude Shannon", "year": 1948, "venue": "Bell Labs", "level": 2, "desc": "信息论奠基，通信原理起源"},
                {"title": "The C Programming Language", "authors": "Kernighan & Ritchie", "year": 1978, "venue": "Prentice Hall", "level": 1, "desc": "C语言原始白皮书"},
                # level 2 - 核心系统论文
                {"title": "End-to-End Arguments in System Design", "authors": "Saltzer et al.", "year": 1984, "venue": "ACM TOCS", "level": 2, "desc": "网络端到端原则，系统设计精髓"},
                {"title": "Bigtable: A Distributed Storage System", "authors": "Chang et al.", "year": 2006, "venue": "OSDI", "level": 3, "desc": "NoSQL数据库原型"},
                {"title": "The UNIX Time-Sharing System", "authors": "Ritchie & Thompson", "year": 1974, "venue": "CACM", "level": 2, "desc": "UNIX操作系统经典"},
                {"title": "The Design of a Practical System for Fault-Tolerant VM", "authors": "Scales et al.", "year": 2010, "venue": "ASPLOS", "level": 3, "desc": "分布式容错VM设计"},
                {"title": "Ethernet: Distributed Packet Switching", "authors": "Metcalfe & Boggs", "year": 1976, "venue": "CACM", "level": 1, "desc": "以太网奠基"},
                {"title": "Relational Model of Data for Large Shared Banks", "authors": "Edgar Codd", "year": 1970, "venue": "CACM", "level": 2, "desc": "关系数据库奠基"},
                {"title": "An Efficient Algorithm for Scalable Sorting", "authors": "Various", "year": 2008, "venue": "ACM", "level": 2, "desc": "现代并行排序算法"},
                {"title": "Paxos Made Simple", "authors": "Leslie Lamport", "year": 2001, "venue": "ACM SIGACT News", "level": 3, "desc": "分布式一致性协议Paxos"},
                # level 3 - 前沿系统论文
                {"title": "Spanner: Google's Globally-Distributed DB", "authors": "Corbett et al.", "year": 2012, "venue": "OSDI", "level": 3, "desc": "Google全球分布式数据库"},
                {"title": "Dynamo: Amazon's Highly Available Key-value Store", "authors": "DeCandia et al.", "year": 2007, "venue": "SOSP", "level": 3, "desc": "Amazon分布式KV存储"},
                {"title": "In Search of an Understandable Consensus Algorithm (Raft)", "authors": "Ongaro & Ousterhout", "year": 2014, "venue": "USENIX ATC", "level": 3, "desc": "Raft一致性协议"},
                {"title": "A Fast File System for UNIX", "authors": "McKusick et al.", "year": 1984, "venue": "ACM TOCS", "level": 3, "desc": "文件系统设计经典"},
                {"title": "Structure and Interpretation of Computer Programs", "authors": "Abelson/Sussman", "year": 1985, "venue": "MIT Press", "level": 1, "desc": "SICP计算机入门经典推荐"},
                {"title": "Computer Systems: A Programmer's Perspective", "authors": "Bryant/O'Hallaron", "year": 2003, "venue": "Prentice Hall", "level": 1, "desc": "CSAPP程序员视角，计算机系统入门"},
            ]
        },
        "english": {
            "name": "英语学习",
            "videos": [
                # level 1
                {"title": "BBC Learning English", "url": "https://www.bbc.co.uk/learningenglish", "platform": "BBC", "duration": "自定进度", "level": 1},
                {"title": "EnglishClass101", "url": "https://www.englishclass101.com/", "platform": "EnglishClass101", "duration": "自定进度", "level": 1},
                {"title": "Rachel s English", "url": "https://www.youtube.com/user/rachelsenglish", "platform": "YouTube", "duration": "~20h", "level": 1},
                {"title": "新概念英语全套", "url": "https://www.bilibili.com/video/BV1et4y1f74M", "platform": "B站", "duration": "~60h", "level": 1},
                {"title": "新东方四级词汇", "url": "https://www.bilibili.com/video/BV1Y4411G7uX", "platform": "B站", "duration": "~30h", "level": 1},
                {"title": "English with Lucy", "url": "https://www.youtube.com/@EnglishwithLucy", "platform": "YouTube", "duration": "自定进度", "level": 1},
                {"title": "可汗学院 语法", "url": "https://www.khanacademy.org/humanities/grammar", "platform": "Khan Academy", "duration": "自定进度", "level": 1},
                {"title": "TED Talks (英语字幕)", "url": "https://www.ted.com/talks", "platform": "TED", "duration": "每集~15min", "level": 2},
                # level 2
                {"title": "Coursera Academic English", "url": "https://www.coursera.org/specializations/academic-english", "platform": "Coursera", "duration": "~40h", "level": 2},
                {"title": "雅思7分精讲", "url": "https://www.bilibili.com/video/BV1dD421R7Hd", "platform": "B站", "duration": "~50h", "level": 2},
                {"title": "ETS 托福官方教程", "url": "https://www.ets.org/toefl", "platform": "ETS", "duration": "自定进度", "level": 2},
                {"title": "Duolingo 进阶英语", "url": "https://www.duolingo.com/", "platform": "Duolingo", "duration": "自定进度", "level": 1},
                {"title": "British Council 中级英语", "url": "https://learnenglish.britishcouncil.org/", "platform": "British Council", "duration": "自定进度", "level": 2},
                {"title": "VOA慢速英语", "url": "https://learningenglish.voanews.com/", "platform": "VOA", "duration": "每天15分钟", "level": 1},
                {"title": "英语口语训练营", "url": "https://www.bilibili.com/video/BV1qJ411u7t9", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "剑桥高级英语(CAE)", "url": "https://www.cambridgeenglish.org/exams-and-tests/advanced/", "platform": "Cambridge", "duration": "~60h", "level": 3},
                # level 3
                {"title": "GRE 词汇精讲", "url": "https://www.bilibili.com/video/BV1vJ411B7Fv", "platform": "B站", "duration": "~40h", "level": 3},
                {"title": "学术论文写作(Academic Writing)", "url": "https://www.coursera.org/learn/academic-english-writing", "platform": "Coursera", "duration": "~30h", "level": 3},
                {"title": "经济学人精讲", "url": "https://www.bilibili.com/video/BV1aL41187kf", "platform": "B站", "duration": "~20h", "level": 3},
                {"title": "BBC 6 Minute English (高级)", "url": "https://www.bbc.co.uk/programmes/p02pc9pj", "platform": "BBC", "duration": "自定进度", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《英语语法新思维》", "author": "张满胜", "publisher": "群言出版社", "level": 1, "desc": "语法体系全面，入门友好"},
                {"title": "《牛津高阶英汉双解词典》", "author": "Hornby", "publisher": "商务印书馆", "level": 1, "desc": "权威词典必备"},
                {"title": "《新概念英语》1-2册", "author": "L.G. Alexander", "publisher": "外研社", "level": 1, "desc": "经典入门教材"},
                {"title": "《Word Power Made Easy》", "author": "Norman Lewis", "publisher": "Anchor", "level": 2, "desc": "词根词缀扩充词汇"},
                {"title": "《英语在用·剑桥初级语法》", "author": "Murphy", "publisher": "外研社", "level": 1, "desc": "剑桥语法红皮书初级"},
                {"title": "《四级词汇词根联想记忆》", "author": "俞敏洪", "publisher": "新东方", "level": 1, "desc": "CET-4词汇必备"},
                # level 2
                {"title": "《The Elements of Style》", "author": "Strunk & White", "publisher": "Pearson", "level": 3, "desc": "英文写作指南经典"},
                {"title": "《剑桥雅思真题精讲》", "author": "周成刚", "publisher": "新东方", "level": 2, "desc": "雅思备考必备"},
                {"title": "《托福考试备考策略》", "author": "ETS官方", "publisher": "McGraw-Hill", "level": 2, "desc": "托福官方指南"},
                {"title": "《On Writing Well》英文写作", "author": "William Zinsser", "publisher": "Harper", "level": 3, "desc": "英文写作圣经"},
                {"title": "《英语在用·剑桥中级语法》", "author": "Murphy", "publisher": "外研社", "level": 2, "desc": "剑桥语法中级"},
                {"title": "《六级词汇·乱序版》", "author": "俞敏洪", "publisher": "新东方", "level": 2, "desc": "CET-6词汇乱序记忆"},
                # level 3
                {"title": "《GRE词汇精选》(红宝书)", "author": "俞敏洪", "publisher": "新东方", "level": 3, "desc": "GRE词汇备考"},
                {"title": "《韦小绿·韦氏词根词典》", "author": "Merriam-Webster", "publisher": "Merriam-Webster", "level": 3, "desc": "词根词缀进阶"},
                {"title": "《GMAT 官方指南》", "author": "GMAC", "publisher": "Wiley", "level": 3, "desc": "GMAT备考权威"},
                {"title": "《A Manual for Writers of Research Papers》", "author": "Kate Turabian", "publisher": "U Chicago Press", "level": 3, "desc": "学术论文写作指南"},
            ],
            "papers": [
                {"title": "The Role of Input in SLA", "authors": "Stephen Krashen", "year": 1985, "venue": "Applied Linguistics", "level": 1, "desc": "输入假说理论，二语习得奠基入门"},
                {"title": "Communicative Competence Theory", "authors": "Hymes", "year": 1972, "venue": "Linguistics", "level": 3, "desc": "交际能力理论"},
                {"title": "The Natural Approach to Language Learning", "authors": "Krashen & Terrell", "year": 1983, "venue": "Alemany Press", "level": 1, "desc": "自然法语言学习方法论入门"},
                {"title": "Vocabulary Acquisition Research", "authors": "Paul Nation", "year": 2001, "venue": "Cambridge", "level": 2, "desc": "词汇习得研究经典"},
                {"title": "Noticing Hypothesis (Schmidt)", "authors": "Richard Schmidt", "year": 1990, "venue": "Language Learning", "level": 3, "desc": "注意假说语言学理论"},
                {"title": "Task-Based Language Teaching", "authors": "Rod Ellis", "year": 2003, "venue": "Oxford", "level": 2, "desc": "任务型教学法综述"},
                {"title": "English as a Global Language", "authors": "David Crystal", "year": 1997, "venue": "Cambridge", "level": 1, "desc": "英语全球化语言学入门"},
                {"title": "Threshold Level English", "authors": "Van Ek & Trim", "year": 1990, "venue": "Council of Europe", "level": 1, "desc": "CEFR欧洲语言框架入门级标准"},
            ]
        },
        "math": {
            "name": "数学",
            "videos": [
                # level 1
                {"title": "3Blue1Brown 数学本质合集", "url": "https://www.bilibili.com/video/BV1qW411N7nX", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "MIT 18.01 单变量微积分", "url": "https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/", "platform": "MIT OCW", "duration": "~50h", "level": 1},
                {"title": "可汗学院 数学系列", "url": "https://www.khanacademy.org/math", "platform": "Khan Academy", "duration": "自定进度", "level": 1},
                {"title": "高等数学(同济) 基础", "url": "https://www.bilibili.com/video/BV1E4411H73v", "platform": "B站", "duration": "~80h", "level": 1},
                {"title": "MIT 18.02 多变量微积分", "url": "https://ocw.mit.edu/courses/18-02sc-multivariable-calculus-fall-2010/", "platform": "MIT OCW", "duration": "~50h", "level": 2},
                {"title": "Strang 微积分重点", "url": "https://ocw.mit.edu/resources/res-18-006-calculus-revisited-single-variable-calculus-fall-2010/", "platform": "MIT OCW", "duration": "~20h", "level": 1},
                {"title": "线性代数基础(宋浩)", "url": "https://www.bilibili.com/video/BV1aW411Q7x1", "platform": "B站", "duration": "~50h", "level": 1},
                {"title": "概率论与数理统计", "url": "https://www.bilibili.com/video/BV1ot4y1d7ni", "platform": "B站", "duration": "~45h", "level": 1},
                # level 2
                {"title": "Gilbert Strang 线性代数", "url": "https://www.bilibili.com/video/BV1ib411t7YR", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "MIT 18.06 线性代数", "url": "https://ocw.mit.edu/courses/18-06sc-linear-algebra-fall-2011/", "platform": "MIT OCW", "duration": "~40h", "level": 2},
                {"title": "MIT 6.041 概率系统分析", "url": "https://ocw.mit.edu/courses/6-041sc-probabilistic-systems-analysis-and-applied-probability-fall-2010/", "platform": "MIT OCW", "duration": "~40h", "level": 2},
                {"title": "离散数学(刘铎)", "url": "https://www.bilibili.com/video/BV13t4y1k7Ep", "platform": "B站", "duration": "~40h", "level": 2},
                {"title": "常微分方程", "url": "https://www.bilibili.com/video/BV19J411J7AZ", "platform": "B站", "duration": "~35h", "level": 2},
                {"title": "Stanford MATH 51 离散与线性", "url": "https://web.stanford.edu/class/math51/", "platform": "Stanford", "duration": "~40h", "level": 2},
                {"title": "数学分析(陈纪修)", "url": "https://www.bilibili.com/video/BV18W411w7dW", "platform": "B站", "duration": "~100h", "level": 2},
                {"title": "近世代数/抽象代数", "url": "https://www.bilibili.com/video/BV1kx411y7iJ", "platform": "B站", "duration": "~40h", "level": 3},
                # level 3
                {"title": "MIT 18.100 实分析", "url": "https://ocw.mit.edu/courses/18-100a-real-analysis-fall-2020/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "复变函数专题", "url": "https://www.bilibili.com/video/BV1bV411i7aD", "platform": "B站", "duration": "~35h", "level": 3},
                {"title": "泛函分析(HLWU)", "url": "https://www.bilibili.com/video/BV17Z4y1G7h3", "platform": "B站", "duration": "~40h", "level": 3},
                {"title": "拓扑学入门", "url": "https://www.youtube.com/playlist?list=PLdUoSZesY-9OsqfJ7q2u5V3eLqCj_5Z6T", "platform": "YouTube", "duration": "~25h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《高等数学》同济版(上下册)", "author": "同济大学数学系", "publisher": "高等教育出版社", "level": 1, "desc": "经典高数教材，考研首选"},
                {"title": "《线性代数》同济版", "author": "同济大学数学系", "publisher": "高等教育出版社", "level": 1, "desc": "线代标准教材"},
                {"title": "《概率论与数理统计》浙大版", "author": "盛骤、谢式千", "publisher": "高等教育出版社", "level": 2, "desc": "考研通用概率统计"},
                {"title": "《普林斯顿微积分读本》", "author": "Adrian Banner", "publisher": "人民邮电出版社", "level": 1, "desc": "入门友好，读起来轻松"},
                {"title": "《程序员的数学》", "author": "结城浩", "publisher": "人民邮电出版社", "level": 1, "desc": "程序员需要的数学入门"},
                {"title": "《线性代数及其应用》", "author": "David C. Lay", "publisher": "机械工业出版社", "level": 2, "desc": "应用导向线代，例子多"},
                # level 2
                {"title": "《数学分析原理》(Rudin)", "author": "Walter Rudin", "publisher": "McGraw-Hill", "level": 3, "desc": "实分析经典小蓝书"},
                {"title": "《概率论与数理统计》(陈希孺)", "author": "陈希孺", "publisher": "中国科学技术出版社", "level": 2, "desc": "概率统计经典，讲解透彻"},
                {"title": "《线性代数应该这样学》", "author": "Axler", "publisher": "人民邮电出版社", "level": 3, "desc": "线性代数进阶经典"},
                {"title": "《具体数学》", "author": "Graham/Knuth/Patashnik", "publisher": "人民邮电出版社", "level": 3, "desc": "CS数学圣经，Knuth巨著"},
                {"title": "《实变函数论》(周民强)", "author": "周民强", "publisher": "北京大学出版社", "level": 3, "desc": "实变函数经典"},
                {"title": "《复变函数论》(钟玉泉)", "author": "钟玉泉", "publisher": "高等教育出版社", "level": 3, "desc": "复变函数经典教材"},
                # level 3
                {"title": "《数学分析》(Rudin)", "author": "Walter Rudin", "publisher": "McGraw-Hill", "level": 3, "desc": "分析学经典"},
                {"title": "《抽象代数》(Dummit)", "author": "Dummit & Foote", "publisher": "Wiley", "level": 3, "desc": "抽象代数权威参考"},
                {"title": "《拓扑学》(Munkres)", "author": "James Munkres", "publisher": "Prentice Hall", "level": 3, "desc": "拓扑学经典教材"},
                {"title": "《泛函分析》(Kreyszig)", "author": "Erwin Kreyszig", "publisher": "Wiley", "level": 3, "desc": "泛函分析入门友好"},
            ],
            "papers": [
                {"title": "The Unreasonable Effectiveness of Mathematics", "authors": "Eugene Wigner", "year": 1960, "venue": "CPAM", "level": 1, "desc": "数学在自然科学中的超有效性，入门必读"},
                {"title": "On Computable Numbers (Turing)", "authors": "Alan Turing", "year": 1936, "venue": "Lond. Math. Soc.", "level": 3, "desc": "图灵机奠基，可计算性理论"},
                {"title": "Godel's Incompleteness Theorems", "authors": "Kurt Godel", "year": 1931, "venue": "Monatshefte", "level": 3, "desc": "哥德尔不完备定理，数学基础里程碑"},
                {"title": "Poincaré Conjecture Proof", "authors": "Grigori Perelman", "year": 2003, "venue": "ArXiv", "level": 3, "desc": "佩雷尔曼证明庞加莱猜想"},
                {"title": "Riemann Hypothesis Overview", "authors": "Various", "year": 2004, "venue": "AMS", "level": 3, "desc": "黎曼猜想综述，千禧问题"},
                {"title": "Why are Discrete Math Important for CS", "authors": "Knuth", "year": 1998, "venue": "Stanford", "level": 1, "desc": "CS离散数学重要性入门"},
                {"title": "The Mathematical Experience", "authors": "Davis & Hersh", "year": 1981, "venue": "Houghton", "level": 1, "desc": "数学文化与数学哲学入门"},
                {"title": "A Mathematician's Apology", "authors": "G.H. Hardy", "year": 1940, "venue": "Cambridge", "level": 1, "desc": "哈代数学家的辩白，数学精神入门"},
            ]
        },
        "physics": {
            "name": "物理",
            "videos": [
                # level 1
                {"title": "MIT 8.01 经典力学", "url": "https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/", "platform": "MIT OCW", "duration": "~50h", "level": 1},
                {"title": "Crash Course Physics", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtN0ge7yDk_UA0ldZJdhwkoV", "platform": "YouTube", "duration": "~10h", "level": 1},
                {"title": "费曼物理 讲义视频", "url": "https://www.bilibili.com/video/BV1QM411r7mt", "platform": "B站", "duration": "~40h", "level": 2},
                {"title": "大学物理(马文蔚)", "url": "https://www.bilibili.com/video/BV1JE411x71i", "platform": "B站", "duration": "~80h", "level": 1},
                {"title": "可汗学院 物理", "url": "https://www.khanacademy.org/science/physics", "platform": "Khan Academy", "duration": "自定进度", "level": 1},
                {"title": "MIT 8.02 电磁学", "url": "https://ocw.mit.edu/courses/8-02-physics-ii-electricity-and-magnetism-spring-2019/", "platform": "MIT OCW", "duration": "~40h", "level": 1},
                {"title": "热学(北京大学)", "url": "https://www.bilibili.com/video/BV17t4y12754", "platform": "B站", "duration": "~35h", "level": 1},
                {"title": "Brilliant.org 物理", "url": "https://brilliant.org/courses/physics/", "platform": "Brilliant", "duration": "自定进度", "level": 1},
                # level 2
                {"title": "MIT 8.03 振动与波", "url": "https://ocw.mit.edu/courses/8-03sc-physics-iii-vibrations-and-waves-fall-2016/", "platform": "MIT OCW", "duration": "~40h", "level": 2},
                {"title": "光学(赵凯华)", "url": "https://www.bilibili.com/video/BV1M4411x7Jd", "platform": "B站", "duration": "~50h", "level": 2},
                {"title": "量子力学入门(苏汝铿)", "url": "https://www.bilibili.com/video/BV1x4411K7oU", "platform": "B站", "duration": "~40h", "level": 2},
                {"title": "MIT 8.04 量子物理I", "url": "https://ocw.mit.edu/courses/8-04-quantum-physics-i-spring-2013/", "platform": "MIT OCW", "duration": "~45h", "level": 3},
                {"title": "电动力学(郭硕鸿)", "url": "https://www.bilibili.com/video/BV1N4411J7mE", "platform": "B站", "duration": "~50h", "level": 3},
                {"title": "统计力学入门", "url": "https://www.bilibili.com/video/BV1qk4y127Qm", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "MIT 8.09 经典力学进阶", "url": "https://ocw.mit.edu/courses/8-09-classical-mechanics-iii-fall-2014/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "Stanford PHYSICS 110 电磁进阶", "url": "https://explorecourses.stanford.edu/search?q=110%20electromagnetism", "platform": "Stanford", "duration": "~40h", "level": 3},
                # level 3
                {"title": "MIT 8.06 量子物理II", "url": "https://ocw.mit.edu/courses/8-06-quantum-physics-ii-spring-2018/", "platform": "MIT OCW", "duration": "~50h", "level": 3},
                {"title": "Caltech 量子场论", "url": "https://www.pma.caltech.edu/~mcc/Ph127/", "platform": "Caltech", "duration": "~50h", "level": 3},
                {"title": "广义相对论(梁灿彬)", "url": "https://www.bilibili.com/video/BV13w411w7sS", "platform": "B站", "duration": "~60h", "level": 3},
                {"title": "Perimeter 粒子物理", "url": "https://www.perimeterinstitute.ca/video-library", "platform": "Perimeter", "duration": "自定进度", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《费曼物理学讲义》(3册)", "author": "Richard Feynman", "publisher": "上海科学技术出版社", "level": 2, "desc": "物理经典，大师亲授"},
                {"title": "《新概念物理教程》5本", "author": "赵凯华", "publisher": "高等教育出版社", "level": 1, "desc": "国内物理经典教材全套"},
                {"title": "《大学物理》", "author": "张三慧", "publisher": "清华大学出版社", "level": 1, "desc": "大学物理标准教材"},
                {"title": "《物理学基础》(Halliday)", "author": "Halliday/Resnick", "publisher": "Wiley", "level": 1, "desc": "国外经典物理入门"},
                {"title": "《热学》(李椿)", "author": "李椿", "publisher": "人民教育出版社", "level": 1, "desc": "热学经典教材"},
                {"title": "《力学》(舒幼生)", "author": "舒幼生", "publisher": "北京大学出版社", "level": 1, "desc": "力学经典入门"},
                # level 2
                {"title": "《光学》(赵凯华)", "author": "赵凯华/钟锡华", "publisher": "北京大学出版社", "level": 2, "desc": "光学经典权威"},
                {"title": "《量子力学导论》(曾谨言)", "author": "曾谨言", "publisher": "科学出版社", "level": 3, "desc": "国内量子力学经典"},
                {"title": "《电动力学》(郭硕鸿)", "author": "郭硕鸿", "publisher": "人民教育出版社", "level": 3, "desc": "电动力学经典教材"},
                {"title": "《Introduction to Electrodynamics》Griffiths", "author": "David Griffiths", "publisher": "Cambridge", "level": 2, "desc": "Griffiths电动力学经典"},
                {"title": "《量子力学概论》Griffiths", "author": "David Griffiths", "publisher": "Cambridge", "level": 2, "desc": "QM入门友好教材"},
                {"title": "《热力学与统计物理》(汪志诚)", "author": "汪志诚", "publisher": "人民教育出版社", "level": 2, "desc": "热统经典教材"},
                # level 3
                {"title": "《量子场论》(Peskin)", "author": "Peskin & Schroeder", "publisher": "Westview", "level": 3, "desc": "QFT权威标准教材"},
                {"title": "《广义相对论》(Wald)", "author": "Robert Wald", "publisher": "U Chicago Press", "level": 3, "desc": "GR经典教材，研究生级"},
                {"title": "《粒子物理导论》(Griffiths)", "author": "David Griffiths", "publisher": "Wiley", "level": 3, "desc": "粒子物理入门友好"},
                {"title": "《凝聚态物理》(Kittel)", "author": "Charles Kittel", "publisher": "Wiley", "level": 3, "desc": "固体/凝聚态经典"},
            ],
            "papers": [
                {"title": "Zur Elektrodynamik bewegter Korper (SR)", "authors": "Albert Einstein", "year": 1905, "venue": "Annalen der Physik", "level": 3, "desc": "狭义相对论开山论文，奇迹年"},
                {"title": "The Foundation of the General Relativity", "authors": "Albert Einstein", "year": 1915, "venue": "Koniglich Preußische Akad.", "level": 3, "desc": "广义相对论奠基"},
                {"title": "On the Constitution of Atoms and Molecules", "authors": "Niels Bohr", "year": 1913, "venue": "Phil. Mag.", "level": 2, "desc": "玻尔原子模型，量子理论基石"},
                {"title": "Uber den anschaulichen Inhalt QM (Uncertainty)", "authors": "Werner Heisenberg", "year": 1927, "venue": "Zeitschrift für Physik", "level": 3, "desc": "海森堡不确定性原理"},
                {"title": "The Quantum Theory of Optical & Electronical Radiation", "authors": "Schwinger/Feynman", "year": 1948, "venue": "Physical Review", "level": 3, "desc": "QED量子电动力学奠基"},
                {"title": "Observation of Gravitational Waves", "authors": "LIGO Collaboration", "year": 2016, "venue": "Physical Review Letters", "level": 3, "desc": "引力波首次观测发现"},
                {"title": "Higgs Boson Discovery (ATLAS/CMS)", "authors": "CERN Collaboration", "year": 2012, "venue": "Physics Letters B", "level": 2, "desc": "希格斯玻色子发现，标准模型完成"},
                {"title": "The Feynman Lectures on Physics (Notes)", "authors": "Richard Feynman", "year": 1963, "venue": "Caltech", "level": 1, "desc": "费曼讲义，物理入门必读经典"},
                {"title": "Newton's Principia Mathematica (Highlights)", "authors": "Isaac Newton", "year": 1687, "venue": "Royal Society", "level": 1, "desc": "牛顿力学奠基之作，经典物理开端"},
                {"title": "Maxwell's Electromagnetic Field Theory", "authors": "James Clerk Maxwell", "year": 1864, "venue": "Royal Society Phil. Trans.", "level": 1, "desc": "麦克斯韦方程，电磁统一理论"},
            ]
        },
        "chemistry": {
            "name": "化学",
            "videos": [
                # level 1
                {"title": "MIT 5.111 化学原理", "url": "https://ocw.mit.edu/courses/5-111sc-principles-of-chemistry-fall-2014/", "platform": "MIT OCW", "duration": "~40h", "level": 1},
                {"title": "Crash Course Chemistry", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtPHzzYuWy6fYEaX9mQQ8oGr", "platform": "YouTube", "duration": "~10h", "level": 1},
                {"title": "无机化学(宋天佑)", "url": "https://www.bilibili.com/video/BV1Bx411K7tH", "platform": "B站", "duration": "~80h", "level": 1},
                {"title": "无机化学", "url": "https://www.icourse163.org/course/NJU-1001693001", "platform": "中国大学MOOC", "duration": "~35h", "level": 1},
                {"title": "普通化学原理(北大)", "url": "https://www.bilibili.com/video/BV1fx41127pP", "platform": "B站", "duration": "~60h", "level": 1},
                {"title": "可汗学院 Chemistry", "url": "https://www.khanacademy.org/science/chemistry", "platform": "Khan Academy", "duration": "自定进度", "level": 1},
                {"title": "分析化学基础", "url": "https://www.bilibili.com/video/BV1LJ41157hT", "platform": "B站", "duration": "~40h", "level": 1},
                {"title": "有机化学基础", "url": "https://www.icourse163.org/course/PKU-1002794001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                # level 2
                {"title": "有机化学(邢其毅/李艳梅)", "url": "https://www.bilibili.com/video/BV1H4411W7wS", "platform": "B站", "duration": "~120h", "level": 2},
                {"title": "分析化学", "url": "https://www.icourse163.org/course/HUST-1001988001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "物理化学(南大)", "url": "https://www.bilibili.com/video/BV1DJ411678J", "platform": "B站", "duration": "~100h", "level": 2},
                {"title": "Physical Chemistry (MIT)", "url": "https://ocw.mit.edu/courses/5-60-thermodynamics-kinetics-spring-2008/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "结构化学(北大)", "url": "https://www.bilibili.com/video/BV1fx41127pS", "platform": "B站", "duration": "~60h", "level": 3},
                {"title": "生物化学(杨荣武)", "url": "https://www.bilibili.com/video/BV1tW411N7Zt", "platform": "B站", "duration": "~60h", "level": 2},
                {"title": "MIT 5.60 热力学动力学", "url": "https://ocw.mit.edu/courses/5-60-thermodynamics-kinetics-spring-2008/", "platform": "MIT OCW", "duration": "~40h", "level": 2},
                {"title": "化学反应工程", "url": "https://www.icourse163.org/course/TJU-1002011001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                # level 3
                {"title": "高等有机化学", "url": "https://www.bilibili.com/video/BV1aK4y147Yw", "platform": "B站", "duration": "~50h", "level": 3},
                {"title": "量子化学", "url": "https://www.bilibili.com/video/BV1Qx411H7eA", "platform": "B站", "duration": "~45h", "level": 3},
                {"title": "MIT 5.03 有机化学进阶", "url": "https://ocw.mit.edu/courses/5-03-principles-of-organic-synthesis-ii-spring-2015/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "高分子化学(浙大)", "url": "https://www.bilibili.com/video/BV14t411P7sK", "platform": "B站", "duration": "~50h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《普通化学原理》", "author": "华彤文", "publisher": "北京大学出版社", "level": 1, "desc": "化学入门经典"},
                {"title": "《无机化学》", "author": "宋天佑", "publisher": "高等教育出版社", "level": 1, "desc": "无机化学标准教材"},
                {"title": "《无机化学》(上/下册)", "author": "北京师范大学", "publisher": "高等教育出版社", "level": 1, "desc": "权威无机教材，北师大三校合编"},
                {"title": "《分析化学》(武大)", "author": "武汉大学", "publisher": "高等教育出版社", "level": 2, "desc": "分析化学经典"},
                {"title": "《化学原理》", "author": "Zumdahl", "publisher": "Brooks/Cole", "level": 1, "desc": "国外经典教材，入门友好"},
                {"title": "《Organic Chemistry》(Klein)", "author": "David Klein", "publisher": "Wiley", "level": 2, "desc": "有机化学入门友好，机制讲解清晰"},
                # level 2
                {"title": "《有机化学》(邢其毅)", "author": "邢其毅/裴伟伟", "publisher": "高等教育出版社", "level": 2, "desc": "有机化学权威教材，经典大本"},
                {"title": "《物理化学》(南大傅献彩)", "author": "傅献彩", "publisher": "高等教育出版社", "level": 2, "desc": "国内物化经典教材"},
                {"title": "《物理化学》", "author": "Atkins", "publisher": "Oxford", "level": 3, "desc": "国际公认物理化学经典"},
                {"title": "《生物化学》(王镜岩)", "author": "王镜岩", "publisher": "高等教育出版社", "level": 2, "desc": "国内生化权威"},
                {"title": "《结构化学基础》(周公度)", "author": "周公度", "publisher": "北京大学出版社", "level": 2, "desc": "结构化学入门"},
                {"title": "《高分子化学》(潘祖仁)", "author": "潘祖仁", "publisher": "化学工业出版社", "level": 2, "desc": "高分子化学经典"},
                # level 3
                {"title": "《高等有机化学》(Carey)", "author": "Carey & Sundberg", "publisher": "Springer", "level": 3, "desc": "高等有机权威"},
                {"title": "《量子化学》(Levine)", "author": "Ira Levine", "publisher": "Pearson", "level": 3, "desc": "量子化学经典"},
                {"title": "《有机合成》(Corey经典)", "author": "E.J. Corey", "publisher": "Wiley", "level": 3, "desc": "合成大师Corey方法论"},
                {"title": "《谱学导论》(宁永成)", "author": "宁永成", "publisher": "清华大学出版社", "level": 3, "desc": "NMR/IR/MS解析必备"},
            ],
            "papers": [
                {"title": "The Structure of Scientific Revolutions", "authors": "Thomas Kuhn", "year": 1962, "venue": "U Chicago Press", "level": 1, "desc": "科学哲学入门，化学研究范式变革"},
                {"title": "Nobel Lectures in Chemistry", "authors": "Various", "year": 2000, "venue": "World Scientific", "level": 3, "desc": "诺贝尔化学奖演讲集"},
                {"title": "The Nature of the Chemical Bond", "authors": "Linus Pauling", "year": 1939, "venue": "Cornell U Press", "level": 2, "desc": "化学键本质，Pauling经典"},
                {"title": "Synthesis of the B12 Vitamin (Woodward)", "authors": "Woodward/Eschenmoser", "year": 1973, "venue": "Helv. Chim. Acta", "level": 3, "desc": "有机合成里程碑"},
                {"title": "The Discovery of Crown Ethers", "authors": "Charles Pedersen", "year": 1967, "venue": "JACS", "level": 3, "desc": "超分子化学开拓"},
                {"title": "CRISPR-Cas9 Genome Editing", "authors": "Doudna & Charpentier", "year": 2012, "venue": "Science", "level": 3, "desc": "基因编辑诺贝尔化学奖成果"},
                {"title": "The Periodic Law (Mendeleev)", "authors": "Dmitri Mendeleev", "year": 1869, "venue": "Rus. Chem. Soc.", "level": 1, "desc": "元素周期表奠基，化学入门必读"},
                {"title": "Organic Synthesis (E.J. Corey)", "authors": "E.J. Corey", "year": 1972, "venue": "Angew. Chem.", "level": 3, "desc": "逆合成分析法开创"},
                {"title": "Some Basic Principles of Chemistry (Introduction)", "authors": "Linus Pauling", "year": 1947, "venue": "General Chemistry", "level": 1, "desc": "化学基本原理入门导读"},
            ]
        },
        "biology": {
            "name": "生物学",
            "videos": [
                # level 1
                {"title": "Crash Course Biology", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtPWfR6I78x0y75H3qI7W9rY", "platform": "YouTube", "duration": "~15h", "level": 1},
                {"title": "MIT 7.012 基础生物学", "url": "https://ocw.mit.edu/courses/7-012-introduction-to-biology-fall-2004/", "platform": "MIT OCW", "duration": "~40h", "level": 1},
                {"title": "可汗学院 生物学", "url": "https://www.khanacademy.org/science/biology", "platform": "Khan Academy", "duration": "自定进度", "level": 1},
                {"title": "普通生物学(北大)", "url": "https://www.bilibili.com/video/BV1BJ411F7zH", "platform": "B站", "duration": "~70h", "level": 1},
                {"title": "陈阅增普通生物学", "url": "https://www.icourse163.org/course/ZZU-1001906001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "细胞生物学(翟中和)", "url": "https://www.bilibili.com/video/BV1VJ411X76j", "platform": "B站", "duration": "~60h", "level": 2},
                {"title": "细胞生物学", "url": "https://www.icourse163.org/course/ZJU-1001985001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "遗传学(刘祖洞)", "url": "https://www.bilibili.com/video/BV1EJ411S74d", "platform": "B站", "duration": "~50h", "level": 2},
                # level 2
                {"title": "遗传学", "url": "https://www.icourse163.org/course/FJNU-1002088001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "生物化学(杨荣武)", "url": "https://www.bilibili.com/video/BV1tW411N7Zt", "platform": "B站", "duration": "~60h", "level": 2},
                {"title": "分子生物学", "url": "https://www.bilibili.com/video/BV1Xx411K7zQ", "platform": "B站", "duration": "~50h", "level": 2},
                {"title": "生态学", "url": "https://www.icourse163.org/course/XMU-1002078001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "MIT 7.016 分子生物学", "url": "https://ocw.mit.edu/courses/7-016-introductory-biology-fall-2018/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "生理学(朱大年)", "url": "https://www.bilibili.com/video/BV1rW411X7oK", "platform": "B站", "duration": "~60h", "level": 2},
                {"title": "微生物学(周德庆)", "url": "https://www.bilibili.com/video/BV19W411X7v9", "platform": "B站", "duration": "~50h", "level": 2},
                {"title": "生物信息学", "url": "https://www.bilibili.com/video/BV1fW411N71o", "platform": "B站", "duration": "~40h", "level": 3},
                # level 3
                {"title": "MIT 7.05 普通生物化学", "url": "https://ocw.mit.edu/courses/7-05-general-biochemistry-spring-2006/", "platform": "MIT OCW", "duration": "~50h", "level": 3},
                {"title": "神经生物学", "url": "https://www.bilibili.com/video/BV1GJ411G7Vq", "platform": "B站", "duration": "~50h", "level": 3},
                {"title": "Harvard MCBI Molecular Biology", "url": "https://www.extension.harvard.edu/", "platform": "Harvard", "duration": "~45h", "level": 3},
                {"title": "Stanford CS229 生物方向机器学习", "url": "https://see.stanford.edu/", "platform": "Stanford", "duration": "~30h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《普通生物学》", "author": "陈阅增", "publisher": "高等教育出版社", "level": 1, "desc": "生物学入门经典"},
                {"title": "《Biology》Campbell", "author": "Campbell/Urry", "publisher": "Pearson", "level": 1, "desc": "国外生物学经典教材"},
                {"title": "《细胞生物学》", "author": "翟中和", "publisher": "高等教育出版社", "level": 2, "desc": "细胞生物学经典"},
                {"title": "《遗传学》(刘祖洞)", "author": "刘祖洞", "publisher": "高等教育出版社", "level": 2, "desc": "遗传学经典入门"},
                {"title": "《Gene X》(基因X)", "author": "Benjamin Lewin", "publisher": "Pearson", "level": 3, "desc": "遗传学权威巨著"},
                {"title": "《生理学》(朱大年)", "author": "朱大年", "publisher": "人民卫生出版社", "level": 2, "desc": "生理学标准教材"},
                # level 2
                {"title": "《分子生物学》", "author": "Robert Weaver", "publisher": "McGraw-Hill", "level": 2, "desc": "分子生物学经典"},
                {"title": "《生物化学》(王镜岩)", "author": "王镜岩", "publisher": "高等教育出版社", "level": 2, "desc": "国内生化权威"},
                {"title": "《Molecular Biology of the Cell》", "author": "Alberts et al.", "publisher": "Garland", "level": 3, "desc": "细胞分子生物学圣经"},
                {"title": "《生态学》", "author": "李博", "publisher": "高等教育出版社", "level": 2, "desc": "生态学权威"},
                {"title": "《微生物学》(沈萍)", "author": "沈萍/陈向东", "publisher": "高等教育出版社", "level": 2, "desc": "微生物学经典"},
                {"title": "《神经生物学》(寿天德)", "author": "寿天德", "publisher": "高等教育出版社", "level": 3, "desc": "神经生物学权威"},
                # level 3
                {"title": "《Gene Essential》基因精髓", "author": "Benjamin Lewin", "publisher": "Jones & Bartlett", "level": 3, "desc": "分子遗传学经典"},
                {"title": "《Immunobiology》Janeway", "author": "Janeway et al.", "publisher": "Garland", "level": 3, "desc": "免疫学权威圣经"},
                {"title": "《Biochemistry》Lehninger", "author": "Lehninger/Cox", "publisher": "Freeman", "level": 3, "desc": "生化经典Lehninger"},
                {"title": "《Evolution》(演化)", "author": "Futuyma", "publisher": "Sinauer", "level": 3, "desc": "进化生物学权威"},
            ],
            "papers": [
                {"title": "Molecular Structure of Nucleic Acids", "authors": "Watson & Crick", "year": 1953, "venue": "Nature", "level": 2, "desc": "DNA双螺旋结构发现，分子生物学开端"},
                {"title": "The Origin of Species", "authors": "Charles Darwin", "year": 1859, "venue": "John Murray", "level": 1, "desc": "进化论经典巨著，生物学入门必读"},
                {"title": "CRISPR-Cas9 Genome Editing", "authors": "Doudna & Charpentier", "year": 2012, "venue": "Science", "level": 3, "desc": "CRISPR基因编辑奠基"},
                {"title": "The Structure of the Potassium Channel", "authors": "Roderick MacKinnon", "year": 1998, "venue": "Science", "level": 3, "desc": "离子通道结构，诺奖成果"},
                {"title": "Human Genome Sequence Draft", "authors": "IHGSC/Celera", "year": 2001, "venue": "Nature/Science", "level": 3, "desc": "人类基因组计划完成"},
                {"title": "mRNA Vaccine Technology", "authors": "Karikó & Weissman", "year": 2005, "venue": "Immunity", "level": 2, "desc": "mRNA疫苗诺奖成果"},
                {"title": "The Endosymbiotic Theory", "authors": "Lynn Margulis", "year": 1967, "venue": "J Theor Biol", "level": 1, "desc": "内共生假说，线粒体/叶绿体起源，入门"},
                {"title": "The Central Dogma of Molecular Biology", "authors": "Francis Crick", "year": 1958, "venue": "Symp. Soc. Exp. Biol.", "level": 1, "desc": "中心法则提出，分子生物学入门"},
                {"title": "The Cell (Molecular Biology of the Cell)", "authors": "Alberts et al.", "year": 1983, "venue": "Garland", "level": 1, "desc": "细胞生物学经典入门导读"},
            ]
        },
        "medicine": {
            "name": "医学",
            "videos": [
                # level 1
                {"title": "医学导论", "url": "https://www.icourse163.org/course/XJTU-1001908001", "platform": "中国大学MOOC", "duration": "~20h", "level": 1},
                {"title": "系统解剖学", "url": "https://www.bilibili.com/video/BV1xE411T7pB", "platform": "B站", "duration": "~50h", "level": 1},
                {"title": "组织学与胚胎学", "url": "https://www.icourse163.org/course/SMU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "生理学(医学)", "url": "https://www.icourse163.org/course/HUST-1002628001", "platform": "中国大学MOOC", "duration": "~35h", "level": 1},
                {"title": "生物化学(医学)", "url": "https://www.icourse163.org/course/BJMU-1002170001", "platform": "中国大学MOOC", "duration": "~35h", "level": 1},
                {"title": "病理学", "url": "https://www.icourse163.org/course/FJMU-1002008001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "药理学", "url": "https://www.icourse163.org/course/SDU-1002026001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "医学微生物学", "url": "https://www.icourse163.org/course/SMU-1002406001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                # level 2
                {"title": "Harvard Medical School Courses", "url": "https://online-learning.hms.harvard.edu/", "platform": "Harvard", "duration": "自定进度", "level": 2},
                {"title": "人体解剖学", "url": "https://www.icourse163.org/course/NTU-1001707001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "生理学(朱大年)", "url": "https://www.bilibili.com/video/BV1rW411X7oK", "platform": "B站", "duration": "~60h", "level": 2},
                {"title": "医学免疫学", "url": "https://www.icourse163.org/course/BJMU-1001916001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "Khan Academy Medicine", "url": "https://www.khanacademy.org/science/medicine", "platform": "Khan Academy", "duration": "自定进度", "level": 2},
                {"title": "诊断学", "url": "https://www.icourse163.org/course/TJMU-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "病理生理学", "url": "https://www.icourse163.org/course/CQMU-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "医学统计学", "url": "https://www.icourse163.org/course/CUMT-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                # level 3
                {"title": "外科学总论", "url": "https://www.bilibili.com/video/BV1MJ411p7yB", "platform": "B站", "duration": "~40h", "level": 3},
                {"title": "内科学(呼吸/循环)", "url": "https://www.icourse163.org/course/SUDA-1002086001", "platform": "中国大学MOOC", "duration": "~40h", "level": 3},
                {"title": "外科学", "url": "https://www.icourse163.org/course/SZU-1002016001", "platform": "中国大学MOOC", "duration": "~40h", "level": 3},
                {"title": "妇产科学", "url": "https://www.icourse163.org/course/CQMU-1002076001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "循证医学", "url": "https://www.icourse163.org/course/FJMU-1002416001", "platform": "中国大学MOOC", "duration": "~25h", "level": 3},
                {"title": "临床流行病学", "url": "https://www.icourse163.org/course/ZJU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "儿科学", "url": "https://www.icourse163.org/course/SHSMU-1002026001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "急诊医学", "url": "https://www.icourse163.org/course/FJMU-1002066001", "platform": "中国大学MOOC", "duration": "~25h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《系统解剖学》", "author": "柏树令", "publisher": "人民卫生出版社", "level": 1, "desc": "解剖学标准教材"},
                {"title": "《组织学与胚胎学》", "author": "邹仲之", "publisher": "人民卫生出版社", "level": 1, "desc": "组胚标准教材"},
                {"title": "《生理学》", "author": "朱大年", "publisher": "人民卫生出版社", "level": 1, "desc": "生理学经典"},
                {"title": "《生物化学与分子生物学》", "author": "周春燕", "publisher": "人民卫生出版社", "level": 1, "desc": "生化标准教材"},
                {"title": "《病理学》", "author": "李玉林", "publisher": "人民卫生出版社", "level": 1, "desc": "病理学经典"},
                {"title": "《药理学》", "author": "杨宝峰", "publisher": "人民卫生出版社", "level": 1, "desc": "药理学权威"},
                # level 2
                {"title": "《病理生理学》", "author": "王建枝", "publisher": "人民卫生出版社", "level": 2, "desc": "病生标准教材"},
                {"title": "《医学微生物学》", "author": "李凡", "publisher": "人民卫生出版社", "level": 2, "desc": "微生物经典"},
                {"title": "《医学免疫学》", "author": "曹雪涛", "publisher": "人民卫生出版社", "level": 2, "desc": "免疫学权威"},
                {"title": "《诊断学》", "author": "万学红/卢雪峰", "publisher": "人民卫生出版社", "level": 2, "desc": "诊断学经典"},
                {"title": "《医学统计学》", "author": "李康", "publisher": "人民卫生出版社", "level": 2, "desc": "医学统计权威"},
                {"title": "《内科学》(八年制)", "author": "王吉耀", "publisher": "人民卫生出版社", "level": 3, "desc": "内科学权威八年制"},
                {"title": "《外科学》(八年制)", "author": "陈孝平", "publisher": "人民卫生出版社", "level": 3, "desc": "外科学标准教材"},
                {"title": "《实用内科学》", "author": "林果为", "publisher": "人民卫生出版社", "level": 3, "desc": "内科工具书巨著"},
                # level 3
                {"title": "《妇产科学》", "author": "谢幸/孔北华", "publisher": "人民卫生出版社", "level": 3, "desc": "妇产科学权威"},
                {"title": "《儿科学》", "author": "王卫平", "publisher": "人民卫生出版社", "level": 3, "desc": "儿科学标准教材"},
                {"title": "《Harrison's Principles of Internal Medicine》", "author": "Longo et al.", "publisher": "McGraw-Hill", "level": 3, "desc": "内科学国际权威圣经"},
                {"title": "《Guyton and Hall Textbook of Medical Physiology》", "author": "Hall", "publisher": "Elsevier", "level": 3, "desc": "生理学国际权威"},
            ],
            "papers": [
                {"title": "The Lancet Medical Journals", "authors": "Various", "year": 1823, "venue": "Elsevier", "level": 2, "desc": "医学顶级期刊"},
                {"title": "New England Journal of Medicine", "authors": "Various", "year": 1812, "venue": "NEJM", "level": 2, "desc": "医学权威期刊"},
                {"title": "Flexner Report on Medical Education", "authors": "Abraham Flexner", "year": 1910, "venue": "Carnegie Foundation", "level": 1, "desc": "现代医学教育制度改革奠基"},
                {"title": "Discovery of Penicillin", "authors": "Alexander Fleming", "year": 1929, "venue": "British Journal of Experimental Pathology", "level": 1, "desc": "青霉素发现，抗生素时代入门"},
                {"title": "DNA Double Helix (med relevance)", "authors": "Watson & Crick", "year": 1953, "venue": "Nature", "level": 2, "desc": "分子医学基础"},
                {"title": "Evidence-Based Medicine Manifesto", "authors": "Sackett et al.", "year": 1996, "venue": "BMJ", "level": 1, "desc": "循证医学入门，临床实践必读"},
                {"title": "First COVID-19 Vaccine Efficacy", "authors": "Pfizer/BioNTech Group", "year": 2020, "venue": "NEJM", "level": 3, "desc": "mRNA疫苗临床疗效"},
                {"title": "Structure of the SARS-CoV-2 Spike", "authors": "Wrapp et al.", "year": 2020, "venue": "Science", "level": 3, "desc": "新冠病毒Spike结构解析"},
                {"title": "On the Origin of Species (医学影响)", "authors": "Charles Darwin", "year": 1859, "venue": "Murray", "level": 1, "desc": "进化论对医学的影响，入门必读"},
                {"title": "The Emperor of All Maladies", "authors": "Siddhartha Mukherjee", "year": 2010, "venue": "Scribner", "level": 1, "desc": "众病之王癌症传，通俗医学入门"},
            ]
        },
        "finance": {
            "name": "金融",
            "videos": [
                # level 1
                {"title": "耶鲁大学 金融市场", "url": "https://www.coursera.org/learn/finance-markets", "platform": "Coursera", "duration": "~20h", "level": 1},
                {"title": "可汗学院 金融学", "url": "https://www.khanacademy.org/economics-finance-domain", "platform": "Khan Academy", "duration": "自定进度", "level": 1},
                {"title": "货币银行学", "url": "https://www.bilibili.com/video/BV1nE411T7wW", "platform": "B站", "duration": "~40h", "level": 1},
                {"title": "金融市场学(张亦春)", "url": "https://www.icourse163.org/course/HUST-1002636001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "公司金融基础", "url": "https://www.icourse163.org/course/TSINGHUA-1002006001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "WQU 金融量化基础", "url": "https://www.wqu.edu/programs/data-science/", "platform": "WQU", "duration": "~40h", "level": 2},
                {"title": "商业银行经营管理", "url": "https://www.icourse163.org/course/ZJU-1001946001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "国际金融", "url": "https://www.icourse163.org/course/RUC-1001968001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                # level 2
                {"title": "MIT 18.S096 金融工程", "url": "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/", "platform": "MIT OCW", "duration": "~30h", "level": 2},
                {"title": "金融工程", "url": "https://www.icourse163.org/course/SHUFE-1002009001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "投资学(博迪)", "url": "https://www.icourse163.org/course/SWUFE-1002046001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "金融风险管理", "url": "https://www.icourse163.org/course/SZU-1002036001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "CFA Level 1 系统课", "url": "https://www.bilibili.com/video/BV1kT4y1G7mZ", "platform": "B站", "duration": "~80h", "level": 2},
                {"title": "固定收益证券", "url": "https://www.icourse163.org/course/RUC-1002046001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "量化投资", "url": "https://www.icourse163.org/course/FDU-1002046001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "Stanford MS&E 245 金融数学", "url": "https://web.stanford.edu/class/msande245/", "platform": "Stanford", "duration": "~40h", "level": 3},
                # level 3
                {"title": "MIT 15.401 金融理论", "url": "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2017/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "金融经济学(北大)", "url": "https://www.bilibili.com/video/BV1WJ411B7eT", "platform": "B站", "duration": "~40h", "level": 3},
                {"title": "行为金融学", "url": "https://www.icourse163.org/course/SJTU-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "Algorithmic Trading (QuantConnect)", "url": "https://www.quantconnect.com/learning", "platform": "QuantConnect", "duration": "自定进度", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《货币银行学》", "author": "易纲/吴有昌", "publisher": "格致出版社", "level": 1, "desc": "金融学基础权威"},
                {"title": "《金融学》", "author": "黄达/张杰", "publisher": "中国人民大学出版社", "level": 1, "desc": "金融学权威教材"},
                {"title": "《投资学》", "author": "滋维·博迪(Zvi Bodie)", "publisher": "机械工业出版社", "level": 2, "desc": "投资学经典"},
                {"title": "《公司金融》(Ross)", "author": "Stephen Ross", "publisher": "机械工业出版社", "level": 2, "desc": "公司理财权威"},
                {"title": "《金融市场学》", "author": "张亦春", "publisher": "高等教育出版社", "level": 2, "desc": "金融市场经典"},
                {"title": "《Principles of Corporate Finance》", "author": "Brealey/Myers/Allen", "publisher": "McGraw-Hill", "level": 2, "desc": "公司金融国际权威"},
                # level 2
                {"title": "《金融工程》(John Hull)", "author": "John Hull", "publisher": "机械工业出版社", "level": 3, "desc": "金融工程期权期货经典"},
                {"title": "《Options, Futures, and Other Derivatives》", "author": "John Hull", "publisher": "Pearson", "level": 3, "desc": "衍生品圣经Hull原版"},
                {"title": "《风险管理与金融机构》(Hull)", "author": "John Hull", "publisher": "机械工业出版社", "level": 3, "desc": "金融风险管理经典"},
                {"title": "《量化投资》", "author": "Ernie Chan", "publisher": "机械工业出版社", "level": 3, "desc": "量化投资实践经典"},
                {"title": "《国际金融》", "author": "克鲁格曼", "publisher": "中国人民大学出版社", "level": 2, "desc": "国际经济学权威"},
                {"title": "《债券市场：分析与策略》(Fabozzi)", "author": "Frank Fabozzi", "publisher": "中国人民大学出版社", "level": 3, "desc": "固收权威"},
                # level 3
                {"title": "《Asset Pricing》资产定价", "author": "John Cochrane", "publisher": "Princeton", "level": 3, "desc": "资产定价经典教材"},
                {"title": "《Market Risk Analysis》(Alexander)", "author": "Carol Alexander", "publisher": "Wiley", "level": 3, "desc": "市场风险分析权威"},
                {"title": "《Arbitrage Theory in Continuous Time》", "author": "Tomas Björk", "publisher": "Oxford", "level": 3, "desc": "连续时间套利理论金融数学"},
                {"title": "《行为金融学》", "author": "Hersh Shefrin", "publisher": "机械工业出版社", "level": 3, "desc": "行为金融学综合教材"},
            ],
            "papers": [
                {"title": "Modern Portfolio Theory", "authors": "Harry Markowitz", "year": 1952, "venue": "Journal of Finance", "level": 2, "desc": "现代投资组合理论MPT奠基"},
                {"title": "The Black-Scholes Model", "authors": "Black & Scholes", "year": 1973, "venue": "JPE", "level": 3, "desc": "期权定价模型开山"},
                {"title": "CAPM Theory", "authors": "William Sharpe", "year": 1964, "venue": "Journal of Finance", "level": 3, "desc": "资本资产定价模型CAPM"},
                {"title": "Efficient Capital Markets (Fama)", "authors": "Eugene Fama", "year": 1970, "venue": "Journal of Finance", "level": 3, "desc": "有效市场假说EMH综述"},
                {"title": "Prospect Theory (Kahneman/Tversky)", "authors": "Kahneman & Tversky", "year": 1979, "venue": "Econometrica", "level": 3, "desc": "前景理论行为金融基石"},
                {"title": "Modigliani-Miller Theorem", "authors": "Modigliani & Miller", "year": 1958, "venue": "AER", "level": 3, "desc": "MM定理，公司资本结构理论"},
                {"title": "VaR RiskMetrics (JP Morgan)", "authors": "Guldimann et al.", "year": 1994, "venue": "RiskMetrics", "level": 1, "desc": "VaR风险价值方法入门"},
                {"title": "Long-Term Capital Management Collapse", "authors": "Lowenstein", "year": 2000, "venue": "Book/Risk", "level": 1, "desc": "LTCM失败案例研究入门"},
                {"title": "A Random Walk Down Wall Street", "authors": "Burton Malkiel", "year": 1973, "venue": "W.W. Norton", "level": 1, "desc": "随机漫步华尔街，投资入门经典"},
                {"title": "The Intelligent Investor", "authors": "Benjamin Graham", "year": 1949, "venue": "Harper", "level": 1, "desc": "聪明的投资者，价值投资入门必读"},
            ]
        },
        "law": {
            "name": "法学",
            "videos": [
                # level 1
                {"title": "法理学导论", "url": "https://www.icourse163.org/course/ZJU-1001754001", "platform": "中国大学MOOC", "duration": "~20h", "level": 1},
                {"title": "宪法学", "url": "https://www.icourse163.org/course/ZZU-1001709001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "法理学(张文显)", "url": "https://www.bilibili.com/video/BV1XJ411T7sN", "platform": "B站", "duration": "~40h", "level": 1},
                {"title": "中国法制史", "url": "https://www.icourse163.org/course/RUC-1001916001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "Harvard Justice: What's The Right Thing", "url": "https://www.justiceharvard.org/", "platform": "Harvard", "duration": "~24h", "level": 2},
                {"title": "民法总论(韩世远)", "url": "https://www.bilibili.com/video/BV1aJ411Y7cQ", "platform": "B站", "duration": "~40h", "level": 1},
                {"title": "民法学", "url": "https://www.icourse163.org/course/ZJU-1001965001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "刑法学总论(柏浪涛)", "url": "https://www.bilibili.com/video/BV1zT4y1L79x", "platform": "B站", "duration": "~45h", "level": 2},
                # level 2
                {"title": "哈佛法学院课程", "url": "https://www.law.harvard.edu/academics/courses/", "platform": "Harvard", "duration": "自定进度", "level": 2},
                {"title": "刑法学", "url": "https://www.icourse163.org/course/XJTU-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "行政法与行政诉讼法", "url": "https://www.icourse163.org/course/RUC-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "民事诉讼法", "url": "https://www.icourse163.org/course/THU-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "刑事诉讼法", "url": "https://www.icourse163.org/course/SDU-1002036001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "商法学", "url": "https://www.icourse163.org/course/XMU-1002056001", "platform": "中国大学MOOC", "duration": "~40h", "level": 2},
                {"title": "经济法学", "url": "https://www.icourse163.org/course/BJFU-1002076001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "知识产权法", "url": "https://www.icourse163.org/course/SJTU-1002036001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                # level 3
                {"title": "国际法学", "url": "https://www.icourse163.org/course/WHU-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "国际私法学", "url": "https://www.icourse163.org/course/XMU-1002086001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "法律文书写作", "url": "https://www.icourse163.org/course/TSINGHUA-1002056001", "platform": "中国大学MOOC", "duration": "~25h", "level": 3},
                {"title": "Oxford Public International Law", "url": "https://www.law.ox.ac.uk/", "platform": "Oxford", "duration": "自定进度", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《法理学》", "author": "张文显", "publisher": "高等教育出版社", "level": 1, "desc": "法理学经典，全国通用"},
                {"title": "《民法总则》", "author": "王利明", "publisher": "中国人民大学出版社", "level": 1, "desc": "民法基础权威"},
                {"title": "《刑法学》(张明楷)", "author": "张明楷", "publisher": "法律出版社", "level": 2, "desc": "刑法学权威，考研法考必备"},
                {"title": "《宪法学》(张千帆)", "author": "张千帆", "publisher": "北京大学出版社", "level": 1, "desc": "宪法学权威"},
                {"title": "《民法分则》(王利明)", "author": "王利明", "publisher": "中国人民大学出版社", "level": 2, "desc": "民法典分则权威"},
                {"title": "《合同法》(崔建远)", "author": "崔建远", "publisher": "北京大学出版社", "level": 2, "desc": "合同法经典"},
                # level 2
                {"title": "《民事诉讼法》", "author": "张卫平", "publisher": "法律出版社", "level": 3, "desc": "民事诉讼法经典"},
                {"title": "《刑事诉讼法》", "author": "陈光中", "publisher": "北京大学出版社", "level": 3, "desc": "刑事诉讼法权威"},
                {"title": "《行政法与行政诉讼法》", "author": "姜明安", "publisher": "北京大学出版社", "level": 2, "desc": "行政法权威"},
                {"title": "《商法学》", "author": "范健", "publisher": "高等教育出版社", "level": 2, "desc": "商法标准教材"},
                {"title": "《知识产权法》(刘春田)", "author": "刘春田", "publisher": "高等教育出版社", "level": 2, "desc": "知识产权法权威"},
                {"title": "《国际法》", "author": "邵津", "publisher": "北京大学出版社", "level": 2, "desc": "国际法权威"},
                # level 3
                {"title": "《The Concept of Law》", "author": "H.L.A. Hart", "publisher": "Oxford", "level": 3, "desc": "法理学经典法律的概念"},
                {"title": "《Natural Law and Natural Rights》", "author": "John Finnis", "publisher": "Oxford", "level": 3, "desc": "自然法理论"},
                {"title": "《民法思维》(王泽鉴)", "author": "王泽鉴", "publisher": "北京大学出版社", "level": 3, "desc": "民法方法论经典"},
                {"title": "《刑法的基本立场》(张明楷)", "author": "张明楷", "publisher": "商务印书馆", "level": 3, "desc": "刑法学进阶"},
            ],
            "papers": [
                {"title": "The Concept of Law", "authors": "H.L.A. Hart", "year": 1961, "venue": "Oxford", "level": 2, "desc": "法理学经典，实证主义巅峰"},
                {"title": "Natural Law and Natural Rights", "authors": "John Finnis", "year": 1980, "venue": "Oxford", "level": 3, "desc": "新自然法理论"},
                {"title": "The Path of the Law", "authors": "Oliver Wendell Holmes", "year": 1897, "venue": "HRLR", "level": 1, "desc": "法律预测论，法律现实主义先声，入门必读"},
                {"title": "A Theory of Justice (Rawls)", "authors": "John Rawls", "year": 1971, "venue": "Harvard", "level": 3, "desc": "正义论，政治哲学法律基础"},
                {"title": "The Problem of Social Cost (Coase)", "authors": "Ronald Coase", "year": 1960, "venue": "JLE", "level": 3, "desc": "法经济学奠基，科斯定理"},
                {"title": "Taking Rights Seriously", "authors": "Ronald Dworkin", "year": 1977, "venue": "Harvard", "level": 3, "desc": "德沃金权利论，哈特-德沃金论战"},
                {"title": "Declaration of Independence & US Constitution", "authors": "Jefferson/Madison", "year": 1776/1787, "venue": "Founding Docs", "level": 1, "desc": "美国宪政奠基文献，法学入门"},
                {"title": "拿破仑法典/Civil Code(影响)", "authors": "Napoleonic Commission", "year": 1804, "venue": "French", "level": 1, "desc": "大陆法系民法典鼻祖，法学入门"},
                {"title": "法治及其本土资源", "authors": "朱苏力", "year": 1996, "venue": "中国政法大学", "level": 1, "desc": "中国法治本土资源，入门级法学文集"},
                {"title": "论法的精神", "authors": "孟德斯鸠", "year": 1748, "venue": "法国", "level": 1, "desc": "三权分立理论，西方法治思想入门"},
            ]
        },
        "psychology": {
            "name": "心理学",
            "videos": [
                # level 1
                {"title": "耶鲁大学 心理学导论", "url": "https://www.coursera.org/learn/introduction-to-psychology", "platform": "Coursera", "duration": "~20h", "level": 1},
                {"title": "Crash Course Psychology", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtOPRKzVLY0jJY-uHOH9KVU6", "platform": "YouTube", "duration": "~10h", "level": 1},
                {"title": "普通心理学(彭聃龄)", "url": "https://www.bilibili.com/video/BV1XE411P7bZ", "platform": "B站", "duration": "~60h", "level": 1},
                {"title": "心理学与生活", "url": "https://www.icourse163.org/course/HUST-1002456001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "发展心理学", "url": "https://www.icourse163.org/course/BJFU-1002056001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "社会心理学", "url": "https://www.icourse163.org/course/BJUT-1002572001", "platform": "中国大学MOOC", "duration": "~20h", "level": 2},
                {"title": "人格心理学", "url": "https://www.icourse163.org/course/SWJTU-1002076001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "认知心理学", "url": "https://www.icourse163.org/course/ZJU-1002076001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                # level 2
                {"title": "心理咨询与治疗", "url": "https://www.icourse163.org/course/NJU-1002086001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "异常心理学", "url": "https://www.bilibili.com/video/BV1V7411B7xY", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "教育心理学", "url": "https://www.icourse163.org/course/SCNU-1001956001", "platform": "中国大学MOOC", "duration": "~20h", "level": 2},
                {"title": "实验心理学", "url": "https://www.icourse163.org/course/CNU-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "心理统计学", "url": "https://www.icourse163.org/course/BFSU-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "SPSS数据统计", "url": "https://www.bilibili.com/video/BV1kJ411s7Vf", "platform": "B站", "duration": "~25h", "level": 2},
                {"title": "MIT 9.00SC 心理学导论", "url": "https://ocw.mit.edu/courses/9-00sc-introduction-to-psychology-fall-2011/", "platform": "MIT OCW", "duration": "~30h", "level": 2},
                {"title": "积极心理学(哈佛TalBen)", "url": "https://www.bilibili.com/video/BV1Mx411x79L", "platform": "B站", "duration": "~35h", "level": 2},
                # level 3
                {"title": "临床心理学", "url": "https://www.icourse163.org/course/BJFU-1002076001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "认知神经科学", "url": "https://www.bilibili.com/video/BV1MJ411G7uT", "platform": "B站", "duration": "~40h", "level": 3},
                {"title": "Stanford PSYCH 1 心理学", "url": "https://explorecourses.stanford.edu/search?q=PSYCH1", "platform": "Stanford", "duration": "~30h", "level": 3},
                {"title": "R 语言心理统计", "url": "https://www.bilibili.com/video/BV1G7411u7N6", "platform": "B站", "duration": "~25h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《普通心理学》", "author": "彭聃龄", "publisher": "北京师范大学出版社", "level": 1, "desc": "心理学入门权威，考研必备"},
                {"title": "《心理学与生活》", "author": "Philip Zimbardo", "publisher": "人民邮电出版社", "level": 1, "desc": "心理学入门经典，趣味性强"},
                {"title": "《社会心理学》(迈尔斯)", "author": "戴维·迈尔斯", "publisher": "人民邮电出版社", "level": 2, "desc": "社会心理学经典教材"},
                {"title": "《发展心理学》(林崇德)", "author": "林崇德", "publisher": "人民教育出版社", "level": 2, "desc": "发展心理学权威"},
                {"title": "《人格心理学》(黄希庭)", "author": "黄希庭", "publisher": "浙江教育出版社", "level": 1, "desc": "人格心理学经典"},
                {"title": "《An Introduction to History of Psychology》", "author": "Hergenhahn", "publisher": "Cengage", "level": 2, "desc": "心理学史经典"},
                # level 2
                {"title": "《认知心理学》", "author": "王甦/汪安圣", "publisher": "北京大学出版社", "level": 2, "desc": "认知心理学经典"},
                {"title": "《实验心理学》", "author": "郭秀艳", "publisher": "人民教育出版社", "level": 3, "desc": "实验心理学权威"},
                {"title": "《现代心理与教育统计学》", "author": "张厚粲", "publisher": "北京师范大学出版社", "level": 2, "desc": "心理统计经典"},
                {"title": "《变态心理学》(钱铭怡)", "author": "钱铭怡", "publisher": "北京大学出版社", "level": 2, "desc": "异常心理学权威"},
                {"title": "《心理咨询与心理治疗》(钱铭怡)", "author": "钱铭怡", "publisher": "北京大学出版社", "level": 2, "desc": "心理咨询权威"},
                {"title": "《教育心理学》(陈琦刘儒德)", "author": "陈琦/刘儒德", "publisher": "高等教育出版社", "level": 2, "desc": "教育心理学权威"},
                # level 3
                {"title": "《The Interpretation of Dreams》", "author": "Sigmund Freud", "publisher": "国际精神分析", "level": 2, "desc": "精神分析经典，梦的解析"},
                {"title": "《Principles of Psychology》", "author": "William James", "publisher": "Henry Holt", "level": 2, "desc": "心理学原理，威廉·詹姆斯巨著"},
                {"title": "《Cognitive Neuroscience》", "author": "Michael Gazzaniga", "publisher": "Norton", "level": 3, "desc": "认知神经科学权威"},
                {"title": "《Diagnostic and Statistical Manual》DSM-5", "author": "APA", "publisher": "APA", "level": 3, "desc": "精神障碍诊断与统计手册"},
            ],
            "papers": [
                {"title": "The Interpretation of Dreams", "authors": "Sigmund Freud", "year": 1899, "venue": "Leipziger Verlagsanstalt", "level": 2, "desc": "精神分析经典"},
                {"title": "Principles of Psychology", "authors": "William James", "year": 1890, "venue": "Henry Holt", "level": 1, "desc": "心理学学科奠基，入门必读"},
                {"title": "Behaviorist Manifesto (Watson)", "authors": "John Watson", "year": 1913, "venue": "Psychological Review", "level": 2, "desc": "行为主义宣言，心理学范式革命"},
                {"title": "A Behaviorist's Theory of Personality", "authors": "B.F. Skinner", "year": 1953, "venue": "McGraw-Hill", "level": 2, "desc": "斯金纳操作性条件反射"},
                {"title": "Cognitive Revolution (Miller Bruner)", "authors": "George Miller et al.", "year": 1956, "venue": "Psychological Review", "level": 3, "desc": "认知革命奠基论文"},
                {"title": "Prospect Theory", "authors": "Kahneman & Tversky", "year": 1979, "venue": "Econometrica", "level": 2, "desc": "前景理论，决策心理里程碑"},
                {"title": "Stanford Prison Experiment", "authors": "Zimbardo", "year": 1971, "venue": "Naval Research Reviews", "level": 2, "desc": "斯坦福监狱实验情境力量入门"},
                {"title": "Milgram Obedience Experiment", "authors": "Stanley Milgram", "year": 1963, "venue": "J. Abn. Psych.", "level": 2, "desc": "服从权威实验，社会心理学里程碑"},
                {"title": "Flow: The Psychology of Optimal Experience", "authors": "Mihaly Csikszentmihalyi", "year": 1990, "venue": "Harper", "level": 1, "desc": "心流理论，积极心理学入门"},
                {"title": "The Power of Habit (Duhigg)", "authors": "Charles Duhigg", "year": 2012, "venue": "Random House", "level": 1, "desc": "习惯心理学入门，通俗易读"},
            ]
        },
        "economics": {
            "name": "经济学",
            "videos": [
                # level 1
                {"title": "耶鲁大学 经济学原理", "url": "https://www.coursera.org/learn/principles-of-microeconomics", "platform": "Coursera", "duration": "~20h", "level": 1},
                {"title": "MIT 14.01 微观经济学", "url": "https://ocw.mit.edu/courses/14-01sc-principles-of-microeconomics-fall-2011/", "platform": "MIT OCW", "duration": "~40h", "level": 1},
                {"title": "可汗学院 微观/宏观经济学", "url": "https://www.khanacademy.org/economics-finance-domain", "platform": "Khan Academy", "duration": "自定进度", "level": 1},
                {"title": "微观经济学(高鸿业)", "url": "https://www.bilibili.com/video/BV1kt4y1f7Y3", "platform": "B站", "duration": "~50h", "level": 1},
                {"title": "经济学原理(曼昆)", "url": "https://www.icourse163.org/course/HUST-1002656001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "宏观经济学(高鸿业)", "url": "https://www.bilibili.com/video/BV1Kt4y1f7Kz", "platform": "B站", "duration": "~45h", "level": 1},
                {"title": "宏观经济学", "url": "https://www.icourse163.org/course/CQU-1002081001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "MIT 14.02 宏观经济学", "url": "https://ocw.mit.edu/courses/14-02-principles-of-macroeconomics-spring-2014/", "platform": "MIT OCW", "duration": "~40h", "level": 2},
                # level 2
                {"title": "计量经济学(伍德里奇)", "url": "https://www.bilibili.com/video/BV1kJ411s7fU", "platform": "B站", "duration": "~50h", "level": 2},
                {"title": "计量经济学", "url": "https://www.icourse163.org/course/ZJU-1002096001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "国际经济学", "url": "https://www.icourse163.org/course/HUST-1002628001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "博弈论", "url": "https://www.icourse163.org/course/XJTU-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "中级微观经济学(范里安)", "url": "https://www.bilibili.com/video/BV1VJ411H7uM", "platform": "B站", "duration": "~50h", "level": 3},
                {"title": "中级宏观经济学", "url": "https://www.icourse163.org/course/THU-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "劳动经济学", "url": "https://www.icourse163.org/course/RUC-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "Stanford Econ 1 经济学原理", "url": "https://explorecourses.stanford.edu/search?q=econ1", "platform": "Stanford", "duration": "~30h", "level": 2},
                # level 3
                {"title": "高级微观经济学(Varian/Varian)", "url": "https://www.bilibili.com/video/BV1zJ411T7eS", "platform": "B站", "duration": "~60h", "level": 3},
                {"title": "高级宏观经济学(罗默)", "url": "https://www.bilibili.com/video/BV1t7411m7zL", "platform": "B站", "duration": "~50h", "level": 3},
                {"title": "发展经济学", "url": "https://www.icourse163.org/course/TSINGHUA-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "产业组织理论", "url": "https://www.icourse163.org/course/XMU-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《经济学原理》(曼昆)", "author": "曼昆(N.Gregory Mankiw)", "publisher": "北京大学出版社", "level": 1, "desc": "经济学入门经典，畅销全球"},
                {"title": "《西方经济学(微+宏)》", "author": "高鸿业", "publisher": "中国人民大学出版社", "level": 1, "desc": "国内考研权威教材"},
                {"title": "《微观经济学》(平狄克)", "author": "平狄克/鲁宾费尔德", "publisher": "中国人民大学出版社", "level": 2, "desc": "中级微观权威"},
                {"title": "《宏观经济学》(多恩布什)", "author": "多恩布什/费希尔", "publisher": "中国人民大学出版社", "level": 2, "desc": "中级宏观经典"},
                {"title": "《Economics》Sloman/Garratt", "author": "John Sloman", "publisher": "Pearson", "level": 1, "desc": "英国主流经济学入门"},
                {"title": "《生活中的经济学》", "author": "薛兆丰", "publisher": "中信出版社", "level": 1, "desc": "经济学思维通俗入门"},
                # level 2
                {"title": "《计量经济学》(伍德里奇)", "author": "伍德里奇(Wooldridge)", "publisher": "中国人民大学出版社", "level": 3, "desc": "计量经济学经典"},
                {"title": "《计量经济学导论》(古扎拉蒂)", "author": "Damodar Gujarati", "publisher": "中国人民大学出版社", "level": 3, "desc": "计量另一经典入门"},
                {"title": "《国际经济学》(克鲁格曼)", "author": "克鲁格曼/奥伯斯法尔德", "publisher": "中国人民大学出版社", "level": 2, "desc": "国际经济学权威"},
                {"title": "《博弈论》(Gibbons)", "author": "Robert Gibbons", "publisher": "中国人民大学出版社", "level": 3, "desc": "博弈论入门权威"},
                {"title": "《微观经济学：现代观点》(范里安)", "author": "Hal Varian", "publisher": "格致出版社", "level": 3, "desc": "中级微观最流行"},
                {"title": "《宏观经济学》(曼昆)", "author": "曼昆", "publisher": "中国人民大学出版社", "level": 3, "desc": "中级宏观曼昆版"},
                # level 3
                {"title": "《An Inquiry into the Nature》国富论", "author": "Adam Smith", "publisher": "W. Strahan", "level": 2, "desc": "经济学奠基之作国富论"},
                {"title": "《General Theory》就业利息货币通论", "author": "John Keynes", "publisher": "Macmillan", "level": 3, "desc": "凯恩斯革命宏观经济学起源"},
                {"title": "《Capital》资本论", "author": "Karl Marx", "publisher": "Dietz Verlag", "level": 3, "desc": "马克思政治经济学巨著"},
                {"title": "《Advanced Microeconomic Theory》", "author": "Jehle/Reny", "publisher": "Pearson", "level": 3, "desc": "高级微观经济学标准"},
            ],
            "papers": [
                {"title": "An Inquiry into the Nature(W.of Nations)", "authors": "Adam Smith", "year": 1776, "venue": "W. Strahan", "level": 1, "desc": "经济学奠基之作国富论，入门必读"},
                {"title": "The General Theory (Keynes)", "authors": "John Keynes", "year": 1936, "venue": "Macmillan", "level": 2, "desc": "宏观经济学创立"},
                {"title": "Das Kapital Vol.1", "authors": "Karl Marx", "year": 1867, "venue": "Hamburg", "level": 3, "desc": "资本论，剩余价值理论"},
                {"title": "The Problem of Social Cost(Coase)", "authors": "Ronald Coase", "year": 1960, "venue": "JLE", "level": 2, "desc": "科斯定理，法经济学"},
                {"title": "A Theory of Production(Cobb-Douglas)", "authors": "Cobb & Douglas", "year": 1928, "venue": "AER", "level": 1, "desc": "柯布-道格拉斯生产函数入门"},
                {"title": "The Uses of Literacy(Granovetter)", "authors": "Mark Granovetter", "year": 1973, "venue": "AJS", "level": 3, "desc": "弱关系强度社会资本"},
                {"title": "Endogenous Growth(Romer/Lucas)", "authors": "Paul Romer", "year": 1990, "venue": "JPE", "level": 3, "desc": "内生增长理论，Romer模型"},
                {"title": "Nudge (Behavioral Econ.)", "authors": "Thaler & Sunstein", "year": 2008, "venue": "Yale UP", "level": 1, "desc": "助推理论行为经济学应用入门"},
                {"title": "Freakonomics (Levitt & Dubner)", "authors": "Steven Levitt", "year": 2005, "venue": "William Morrow", "level": 1, "desc": "魔鬼经济学，经济学思维入门"},
                {"title": "Economics in One Lesson", "authors": "Henry Hazlitt", "year": 1946, "venue": "Harper", "level": 1, "desc": "一课经济学，通俗入门经典"},
            ]
        },
        "engineering": {
            "name": "工程学",
            "videos": [
                # level 1
                {"title": "工程导论", "url": "https://www.icourse163.org/course/HIT-1001971001", "platform": "中国大学MOOC", "duration": "~15h", "level": 1},
                {"title": "工程力学", "url": "https://www.icourse163.org/course/HUST-1002619002", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "Crash Course Engineering", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtO4A_tL6DLZRotxEb114cMR", "platform": "YouTube", "duration": "~12h", "level": 1},
                {"title": "MIT 2.007 设计与制造", "url": "https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/", "platform": "MIT OCW", "duration": "~50h", "level": 2},
                {"title": "材料力学", "url": "https://www.icourse163.org/course/ZJU-1001995001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "流体力学", "url": "https://www.icourse163.org/course/HUST-1002618001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "机械设计基础", "url": "https://www.icourse163.org/course/HIT-1001926001", "platform": "中国大学MOOC", "duration": "~35h", "level": 1},
                {"title": "工程制图", "url": "https://www.icourse163.org/course/SJTU-1001926001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                # level 2
                {"title": "机械原理", "url": "https://www.icourse163.org/course/NWPU-1002006001", "platform": "中国大学MOOC", "duration": "~40h", "level": 2},
                {"title": "热力学", "url": "https://www.icourse163.org/course/XJTU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "控制工程", "url": "https://www.icourse163.org/course/HUST-1002627001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "MIT 2.003 动力学与控制", "url": "https://ocw.mit.edu/courses/2-003sc-engineering-dynamics-fall-2011/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "传热学", "url": "https://www.icourse163.org/course/XJTU-1002076001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "工程材料", "url": "https://www.icourse163.org/course/HUST-1002636001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "有限元分析基础", "url": "https://www.bilibili.com/video/BV1Vx411E7qf", "platform": "B站", "duration": "~30h", "level": 3},
                {"title": "电工电子学(工程)", "url": "https://www.icourse163.org/course/HIT-1001946001", "platform": "中国大学MOOC", "duration": "~40h", "level": 2},
                # level 3
                {"title": "MIT 2.25 流体力学进阶", "url": "https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "机械振动学", "url": "https://www.icourse163.org/course/THU-1002056001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "Stanford ME 300 工程优化", "url": "https://explorecourses.stanford.edu/search?q=me300", "platform": "Stanford", "duration": "~40h", "level": 3},
                {"title": "机器人学导论", "url": "https://www.bilibili.com/video/BV1v4411N7Hj", "platform": "B站", "duration": "~40h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《工程力学》", "author": "范钦珊", "publisher": "高等教育出版社", "level": 1, "desc": "工程力学基础"},
                {"title": "《材料力学》(孙训方)", "author": "孙训方", "publisher": "高等教育出版社", "level": 2, "desc": "材料力学经典"},
                {"title": "《机械设计》", "author": "濮良贵", "publisher": "高等教育出版社", "level": 2, "desc": "机械设计经典"},
                {"title": "《工程材料》", "author": "崔忠圻", "publisher": "机械工业出版社", "level": 2, "desc": "工程材料权威"},
                {"title": "《Fundamentals of Materials Science》", "author": "William Callister", "publisher": "Wiley", "level": 1, "desc": "材料科学与工程权威入门"},
                {"title": "《流体力学》(吴望一)", "author": "吴望一", "publisher": "北京大学出版社", "level": 2, "desc": "流体力学权威"},
                # level 2
                {"title": "《机械原理》(孙桓)", "author": "孙桓", "publisher": "高等教育出版社", "level": 2, "desc": "机械原理经典"},
                {"title": "《工程热力学》(曾丹苓)", "author": "曾丹苓", "publisher": "高等教育出版社", "level": 2, "desc": "工程热力学经典"},
                {"title": "《传热学》(杨世铭/陶文铨)", "author": "杨世铭", "publisher": "高等教育出版社", "level": 3, "desc": "传热学经典教材"},
                {"title": "《自动控制原理》(胡寿松)", "author": "胡寿松", "publisher": "科学出版社", "level": 3, "desc": "控制理论经典教材"},
                {"title": "《Shigley's Mechanical Engineering Design》", "author": "Budynas/Nisbett", "publisher": "McGraw-Hill", "level": 3, "desc": "国际权威机械设计"},
                {"title": "《有限元方法》(Zienkiewicz)", "author": "Zienkiewicz/Taylor", "publisher": "Elsevier", "level": 3, "desc": "有限元分析经典"},
                # level 3
                {"title": "Engineering Design Methods", "authors": "Nigel Cross", "publisher": "Wiley", "level": 2, "desc": "工程设计方法论"},
                {"title": "The Art of Engineering", "authors": "Henry Petroski", "publisher": "Vintage", "level": 2, "desc": "工程艺术与设计思维"},
                {"title": "《机器人学导论》(Craig)", "author": "John Craig", "publisher": "Pearson", "level": 3, "desc": "机器人学经典教材"},
                {"title": "《Heat Transfer》(Incropera)", "author": "Incropera et al.", "publisher": "Wiley", "level": 3, "desc": "国际经典传热学"},
            ],
            "papers": [
                {"title": "Engineering Design Methods", "authors": "Nigel Cross", "year": 1989, "venue": "Wiley", "level": 1, "desc": "工程设计方法论入门经典"},
                {"title": "The Art of Engineering", "authors": "Henry Petroski", "year": 1996, "venue": "Vintage", "level": 2, "desc": "工程失败与设计经验"},
                {"title": "To Engineer Is Human", "authors": "Henry Petroski", "year": 1985, "venue": "St. Martin's", "level": 1, "desc": "设计中失败的作用，入门必读"},
                {"title": "The Federalist Papers of Structural Eng.", "authors": "Mario Salvadori", "year": 1979, "venue": "McGraw-Hill", "level": 1, "desc": "为什么建筑物会站起来，结构入门"},
                {"title": "Finite Element Method Origins", "authors": "Clough/Zienkiewicz", "year": 1965, "venue": "ASEE", "level": 3, "desc": "有限元法开创论文"},
                {"title": "Robotics: Manipulators & Mobility", "authors": "Rodney Brooks", "year": 1996, "venue": "MIT Press", "level": 3, "desc": "机器人学权威综述"},
                {"title": "The Phenomenological Theory of Plasticity", "authors": "Rodney Hill", "year": 1950, "venue": "Clarendon Press", "level": 3, "desc": "塑性理论里程碑"},
                {"title": "Cybernetics (Wiener)", "authors": "Norbert Wiener", "year": 1948, "venue": "MIT Press", "level": 2, "desc": "控制论开创，维纳经典"},
                {"title": "The Way Things Work (Macaulay)", "authors": "David Macaulay", "year": 1988, "venue": "Houghton", "level": 1, "desc": "万物运转的秘密，工程图解入门"},
                {"title": "Design Paradigms: Case Histories", "authors": "Henry Petroski", "year": 1994, "venue": "Cambridge", "level": 1, "desc": "工程设计案例分析入门"},
            ]
        },
        "history": {
            "name": "历史学",
            "videos": [
                # level 1
                {"title": "中国通史", "url": "https://www.icourse163.org/course/XJTU-1001624001", "platform": "中国大学MOOC", "duration": "~40h", "level": 1},
                {"title": "Crash Course World History", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtNjasccl0HtQw6-Eo6bDxl9", "platform": "YouTube", "duration": "~12h", "level": 1},
                {"title": "世界历史", "url": "https://www.icourse163.org/course/SCNU-1001787001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "耶鲁大学 欧洲文明史", "url": "https://www.coursera.org/learn/european-civilization", "platform": "Coursera", "duration": "~25h", "level": 2},
                {"title": "中国古代史专题", "url": "https://www.bilibili.com/video/BV1bx411f76B", "platform": "B站", "duration": "~50h", "level": 1},
                {"title": "中国近代史", "url": "https://www.icourse163.org/course/HUST-1002636001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "史学概论", "url": "https://www.icourse163.org/course/NJU-1002006001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "国史纲要(清华)", "url": "https://www.bilibili.com/video/BV1Qx411a78Y", "platform": "B站", "duration": "~35h", "level": 1},
                # level 2
                {"title": "西方史学史", "url": "https://www.icourse163.org/course/ZJU-1002016001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "考古学概论", "url": "https://www.icourse163.org/course/XMU-1002026001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "中华人民共和国史", "url": "https://www.bilibili.com/video/BV1nE411T7pU", "platform": "B站", "duration": "~40h", "level": 2},
                {"title": "魏晋南北朝史", "url": "https://www.bilibili.com/video/BV1vJ411y7pP", "platform": "B站", "duration": "~35h", "level": 3},
                {"title": "秦汉史专题", "url": "https://www.bilibili.com/video/BV1pJ411J7qg", "platform": "B站", "duration": "~30h", "level": 3},
                {"title": "Yale Open: The American Revolution", "url": "https://oyc.yale.edu/history/hist-116", "platform": "Yale OpenCourses", "duration": "~25h", "level": 2},
                {"title": "Harvard HIST 142 现代中国史", "url": "https://canvas.harvard.edu/", "platform": "Harvard", "duration": "~30h", "level": 3},
                {"title": "中国历史地理", "url": "https://www.icourse163.org/course/FUDAN-1001971001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                # level 3
                {"title": "哈佛 中国古代史专题", "url": "https://academicguides.waldenu.edu/history", "platform": "Harvard", "duration": "~35h", "level": 3},
                {"title": "Oxford History of the Roman Empire", "url": "https://www.conted.ox.ac.uk/", "platform": "Oxford", "duration": "~30h", "level": 3},
                {"title": "剑桥经济史专题", "url": "https://www.cambridge.org/core/", "platform": "Cambridge", "duration": "~30h", "level": 3},
                {"title": "近现代国际关系史", "url": "https://www.icourse163.org/course/RUC-1002046001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《中国古代史》(朱绍侯)", "author": "朱绍侯/齐涛", "publisher": "福建人民出版社", "level": 1, "desc": "中国古代史经典"},
                {"title": "《全球通史》(斯塔夫里阿诺斯)", "author": "斯塔夫里阿诺斯", "publisher": "北京大学出版社", "level": 2, "desc": "全球史权威"},
                {"title": "《万历十五年》", "author": "黄仁宇", "publisher": "中华书局", "level": 2, "desc": "历史研究经典"},
                {"title": "《中国近代史》", "author": "蒋廷黻", "publisher": "中华书局", "level": 2, "desc": "中国近代史经典"},
                {"title": "《史记》(点校本)", "author": "司马迁", "publisher": "中华书局", "level": 2, "desc": "中国史学经典史记"},
                {"title": "《国史大纲》", "author": "钱穆", "publisher": "商务印书馆", "level": 2, "desc": "钱穆通史经典"},
                # level 2
                {"title": "《史学概论》(庞卓恒)", "author": "庞卓恒", "publisher": "高等教育出版社", "level": 2, "desc": "史学理论基础"},
                {"title": "《剑桥中国秦汉史》", "author": "Denis Twitchett", "publisher": "中国社会科学出版社", "level": 3, "desc": "剑桥中国史系列"},
                {"title": "《The Histories》(Herodotus)", "author": "希罗多德", "publisher": "Penguin Classics", "level": 2, "desc": "西方史学之父希罗多德"},
                {"title": "《罗马帝国衰亡史》", "author": "Edward Gibbon", "publisher": "商务印书馆", "level": 3, "desc": "史学名著吉本"},
                {"title": "《History of the Peloponnesian War》", "author": "修昔底德", "publisher": "Hackett", "level": 3, "desc": "伯罗奔尼撒战争史"},
                {"title": "《中国历代政治得失》", "author": "钱穆", "publisher": "三联书店", "level": 2, "desc": "制度史经典钱穆"},
                # level 3
                {"title": "Historiography", "authors": "Georg G. Iggers", "publisher": "Wesleyan", "level": 3, "desc": "史学史权威"},
                {"title": "The Historians' Craft", "authors": "Marc Bloch", "publisher": "Manchester", "level": 2, "desc": "史学方法论"},
                {"title": "《叫魂1768年中国妖术大恐慌》", "author": "孔飞力", "publisher": "上海三联", "level": 3, "desc": "新史学典范"},
                {"title": "《Past and Present》年鉴学派", "author": "Annales School", "publisher": "Vintage", "level": 3, "desc": "年鉴学派代表作品"},
            ],
            "papers": [
                {"title": "Historiography", "authors": "Georg G. Iggers", "year": 1997, "venue": "Wesleyan", "level": 2, "desc": "史学史权威综述"},
                {"title": "The Historians' Craft", "authors": "Marc Bloch", "year": 1949, "venue": "Manchester", "level": 1, "desc": "史学方法论经典入门"},
                {"title": "On History (Fernand Braudel)", "authors": "Fernand Braudel", "year": 1969, "venue": "Mediterranean", "level": 3, "desc": "年鉴学派布罗代尔"},
                {"title": "The Sources of Social Power", "authors": "Michael Mann", "year": 1986, "venue": "Cambridge", "level": 3, "desc": "宏观历史社会学"},
                {"title": "Theses on Feuerbach (Marx)", "authors": "Karl Marx", "year": 1845, "venue": "German Ideology", "level": 2, "desc": "唯物史观奠基"},
                {"title": "The History of the Decline and Fall", "authors": "Edward Gibbon", "year": 1776, "venue": "Strahan & Cadell", "level": 3, "desc": "罗马帝国衰亡史开山"},
                {"title": "The Annales School Manifesto", "authors": "Febvre/Bloch", "year": 1929, "venue": "Annales ESC", "level": 3, "desc": "年鉴学派宣言"},
                {"title": "The Clash of Civilizations", "authors": "Samuel Huntington", "year": 1993, "venue": "Foreign Affairs", "level": 2, "desc": "文明冲突论国际关系史"},
                {"title": "Sapiens: A Brief History of Humankind", "authors": "Yuval Noah Harari", "year": 2011, "venue": "Harper", "level": 1, "desc": "人类简史，通俗世界史入门"},
                {"title": "Guns, Germs, and Steel", "authors": "Jared Diamond", "year": 1997, "venue": "Norton", "level": 1, "desc": "枪炮病菌钢铁，历史地理入门经典"},
            ]
        },
        "music": {
            "name": "音乐",
            "videos": [
                # level 1
                {"title": "音乐基础理论", "url": "https://www.icourse163.org/course/HUBU-1001906001", "platform": "中国大学MOOC", "duration": "~20h", "level": 1},
                {"title": "Music Theory", "url": "https://www.khanacademy.org/humanities/music", "platform": "Khan Academy", "duration": "自定进度", "level": 1},
                {"title": "Crash Course Music Theory", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtQWC1S4TlZsgnQxeqD9cNw5", "platform": "YouTube", "duration": "~12h", "level": 1},
                {"title": "李重光乐理精讲", "url": "https://www.bilibili.com/video/BV1Bx411y76M", "platform": "B站", "duration": "~25h", "level": 1},
                {"title": "西方音乐史", "url": "https://www.icourse163.org/course/CUMTB-1002007001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "中国音乐史", "url": "https://www.icourse163.org/course/BFSU-1002016001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "视唱练耳", "url": "https://www.icourse163.org/course/SCNU-1002006001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "钢琴入门(零基础)", "url": "https://www.bilibili.com/video/BV1pt421f7C7", "platform": "B站", "duration": "~30h", "level": 1},
                # level 2
                {"title": "和声基础", "url": "https://www.icourse163.org/course/HZNU-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "曲式分析", "url": "https://www.icourse163.org/course/NJU-1002056001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "和声学基础", "url": "https://www.bilibili.com/video/BV1rJ411V76d", "platform": "B站", "duration": "~40h", "level": 3},
                {"title": "复调音乐基础", "url": "https://www.icourse163.org/course/CCM-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "配器法入门", "url": "https://www.bilibili.com/video/BV1Hx411C78S", "platform": "B站", "duration": "~25h", "level": 3},
                {"title": "Yale Listening to Music", "url": "https://oyc.yale.edu/music/musi-112", "platform": "Yale OCW", "duration": "~24h", "level": 2},
                {"title": "MIT 21M.301 音乐构成", "url": "https://ocw.mit.edu/courses/21m-301-understanding-music-theory-diatonic-harmony-and-music-form-spring-2019/", "platform": "MIT OCW", "duration": "~25h", "level": 2},
                {"title": "吉他入门教学", "url": "https://www.bilibili.com/video/BV1YJ41177tZ", "platform": "B站", "duration": "~40h", "level": 1},
                # level 3
                {"title": "作曲技法进阶", "url": "https://www.bilibili.com/video/BV1xJ411V7w5", "platform": "B站", "duration": "~35h", "level": 3},
                {"title": "伯克利音乐制作", "url": "https://www.berklee.edu/courses", "platform": "Berklee", "duration": "~30h", "level": 3},
                {"title": "音乐治疗入门", "url": "https://www.bilibili.com/video/BV1HJ411L7tK", "platform": "B站", "duration": "~20h", "level": 3},
                {"title": "电子音乐制作(Ableton)", "url": "https://www.bilibili.com/video/BV1F7411N77K", "platform": "B站", "duration": "~30h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《基本乐理通用教材》", "author": "李重光", "publisher": "高等教育出版社", "level": 1, "desc": "乐理基础经典教材"},
                {"title": "《西方音乐史》(于润洋)", "author": "于润洋", "publisher": "上海音乐出版社", "level": 2, "desc": "西方音乐史经典"},
                {"title": "《中国音乐史纲》", "author": "杨荫浏", "publisher": "人民音乐出版社", "level": 2, "desc": "中国音乐史权威"},
                {"title": "《和声学教程》(斯波索宾)", "author": "斯波索宾", "publisher": "人民音乐出版社", "level": 3, "desc": "和声学经典教材"},
                {"title": "《音乐美学基础》", "author": "张前", "publisher": "中央音乐学院出版社", "level": 2, "desc": "音乐美学基础"},
                {"title": "《How Music Works》(Byrne)", "author": "David Byrne", "publisher": "Canongate", "level": 1, "desc": "音乐如何运作科普"},
                # level 2
                {"title": "《曲式与作品分析》", "author": "吴祖强", "publisher": "人民音乐出版社", "level": 3, "desc": "曲式分析权威"},
                {"title": "《基本乐理》(李重光)", "author": "李重光", "publisher": "高等教育出版社", "level": 1, "desc": "乐理基础教材"},
                {"title": "《复调音乐写作基础》", "author": "陈铭志", "publisher": "人民音乐出版社", "level": 3, "desc": "复调基础教材"},
                {"title": "《The Complete Musician》", "author": "Steven Laitz", "publisher": "Oxford", "level": 2, "desc": "综合乐理教材，国外流行"},
                {"title": "《配器法》(里姆斯基-科萨科夫)", "author": "里姆斯基-科萨科夫", "publisher": "人民音乐出版社", "level": 3, "desc": "配器法经典教材"},
                {"title": "《聆听音乐》(Craig Wright)", "author": "Craig Wright", "publisher": "三联书店", "level": 2, "desc": "耶鲁公开课配套书"},
                # level 3
                {"title": "The Philosophy of Music", "authors": "Peter Kivy", "publisher": "Oxford", "level": 2, "desc": "音乐哲学经典"},
                {"title": "Music in Western Civilization", "authors": "Paul Henry Lang", "publisher": "W.W. Norton", "level": 2, "desc": "西方文明中的音乐"},
                {"title": "《序列音乐写作教程》", "author": "郑英烈", "publisher": "上海音乐出版社", "level": 3, "desc": "20世纪作曲技法"},
                {"title": "《Theory of Harmony》(Schoenberg)", "author": "Arnold Schoenberg", "publisher": "Faber & Faber", "level": 3, "desc": "勋伯格和声学理论"},
            ],
            "papers": [
                {"title": "The Philosophy of Music", "authors": "Peter Kivy", "year": 2002, "venue": "Oxford", "level": 2, "desc": "音乐哲学权威综述"},
                {"title": "Music in Western Civilization", "authors": "Paul Henry Lang", "year": 1941, "venue": "W.W. Norton", "level": 2, "desc": "音乐与西方文明史关系"},
                {"title": "The Rest Is Noise (Ross)", "authors": "Alex Ross", "year": 2007, "venue": "Picador", "level": 1, "desc": "余下的只是噪音，20世纪音乐史入门"},
                {"title": "Beethoven's Heroic Period", "authors": "Lewis Lockwood", "year": 2003, "venue": "Norton", "level": 3, "desc": "贝多芬研究经典"},
                {"title": "Jazz and Its Discontents", "authors": "Gary Giddins", "year": 2004, "venue": "Da Capo", "level": 2, "desc": "爵士文化史"},
                {"title": "The Origins of Music", "authors": "Wallin et al.", "year": 2000, "venue": "MIT Press", "level": 3, "desc": "音乐起源跨学科"},
                {"title": "Absolute Music and The Construction", "authors": "Mark Evan Bonds", "year": 2014, "venue": "Oxford", "level": 3, "desc": "纯音乐美学思想史"},
                {"title": "Why You Like It (Musical Taste)", "authors": "Nolan Gasser", "year": 2019, "venue": "Hachette", "level": 1, "desc": "音乐品味科学解释入门"},
                {"title": "How to Listen to Music (Aaron Copland)", "authors": "Aaron Copland", "year": 1939, "venue": "McGraw-Hill", "level": 1, "desc": "如何欣赏音乐，科普兰入门经典"},
                {"title": "This Is Your Brain on Music", "authors": "Daniel Levitin", "year": 2006, "venue": "Plume", "level": 1, "desc": "音乐与大脑，认知神经科学入门"},
            ]
        },
        "education": {
            "name": "教育学",
            "videos": [
                # level 1
                {"title": "教育学原理", "url": "https://www.icourse163.org/course/BEIJING-NORMAL-1002170001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "普通教育学", "url": "https://www.bilibili.com/video/BV1L7411M7N4", "platform": "B站", "duration": "~50h", "level": 1},
                {"title": "Crash Course Study Skills", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtNcAJRf3bE1IJU6mxMHB-0T", "platform": "YouTube", "duration": "~10h", "level": 1},
                {"title": "教育心理学", "url": "https://www.icourse163.org/course/SCNU-1001956001", "platform": "中国大学MOOC", "duration": "~20h", "level": 2},
                {"title": "教学设计", "url": "https://www.icourse163.org/course/ZJU-1002094001", "platform": "中国大学MOOC", "duration": "~20h", "level": 2},
                {"title": "教育学基础", "url": "https://www.icourse163.org/course/HUST-1002466001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "教育社会学", "url": "https://www.icourse163.org/course/HZNU-1002036001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "中外教育史", "url": "https://www.icourse163.org/course/BNU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                # level 2
                {"title": "教育测量与评价", "url": "https://www.icourse163.org/course/NENU-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "教育研究方法", "url": "https://www.icourse163.org/course/HNU-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "教育经济学", "url": "https://www.icourse163.org/course/HUST-1002606001", "platform": "中国大学MOOC", "duration": "~25h", "level": 3},
                {"title": "教育统计学", "url": "https://www.bilibili.com/video/BV1oJ411J7gE", "platform": "B站", "duration": "~35h", "level": 3},
                {"title": "EdX Learning How to Learn", "url": "https://www.coursera.org/learn/learning-how-to-learn", "platform": "Coursera", "duration": "~15h", "level": 1},
                {"title": "EdX Harvard Life Sciences", "url": "https://pll.harvard.edu/course/education", "platform": "Harvard", "duration": "~20h", "level": 2},
                {"title": "课程与教学论", "url": "https://www.icourse163.org/course/BNU-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "学前教育学", "url": "https://www.icourse163.org/course/NJY-1002016001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                # level 3
                {"title": "高等教育学", "url": "https://www.icourse163.org/course/HUST-1002646001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "比较教育学", "url": "https://www.icourse163.org/course/BNU-1002086001", "platform": "中国大学MOOC", "duration": "~25h", "level": 3},
                {"title": "教育技术学导论", "url": "https://www.icourse163.org/course/BJFU-1002076001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "特殊教育导论", "url": "https://www.icourse163.org/course/BNU-1002026001", "platform": "中国大学MOOC", "duration": "~25h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《教育学》", "author": "王道俊/郭文安", "publisher": "人民教育出版社", "level": 1, "desc": "教育学基础，考研必备"},
                {"title": "《普通教育学》", "author": "赫尔巴特", "publisher": "人民教育出版社", "level": 2, "desc": "教育学经典巨著"},
                {"title": "《教育心理学》", "author": "陈琦/刘儒德", "publisher": "高等教育出版社", "level": 2, "desc": "教育心理学经典"},
                {"title": "《课程与教学论》", "author": "钟启泉/崔允漷", "publisher": "华东师范大学出版社", "level": 2, "desc": "课程论权威"},
                {"title": "《中国教育史》", "author": "孙培青", "publisher": "华东师范大学出版社", "level": 2, "desc": "中国教育史经典"},
                {"title": "《外国教育史教程》", "author": "张斌贤", "publisher": "教育科学出版社", "level": 2, "desc": "外国教育史权威"},
                # level 2
                {"title": "《教育学基础》", "author": "全国十二所重点师范大学", "publisher": "教育科学出版社", "level": 2, "desc": "师范专业通用"},
                {"title": "《教育研究方法导论》", "author": "裴娣娜", "publisher": "安徽教育出版社", "level": 3, "desc": "教育研究方法经典"},
                {"title": "《当代教育学》", "author": "袁振国", "publisher": "教育科学出版社", "level": 2, "desc": "当代教育学综述"},
                {"title": "《Learning How to Learn》", "author": "Barbara Oakley", "publisher": "TarcherPerigee", "level": 1, "desc": "学习方法畅销书"},
                {"title": "《教育测量与评价》", "author": "黄光扬", "publisher": "华东师范大学出版社", "level": 3, "desc": "教育测评权威"},
                {"title": "《Mindset》终身成长", "author": "Carol Dweck", "publisher": "南海出版公司", "level": 1, "desc": "成长型思维模式"},
                # level 3
                {"title": "Democracy and Education", "authors": "John Dewey", "publisher": "Free Press", "level": 2, "desc": "杜威民主主义与教育哲学"},
                {"title": "How Children Learn", "authors": "John Holt", "publisher": "Penguin", "level": 2, "desc": "儿童学习理论经典"},
                {"title": "《教育学文集·教育与社会发展》", "author": "瞿葆奎", "publisher": "人民教育出版社", "level": 3, "desc": "教育文选经典"},
                {"title": "The Structure of Scientific Revolutions (应用)", "author": "Thomas Kuhn", "publisher": "Chicago", "level": 3, "desc": "教育范式研究参考"},
            ],
            "papers": [
                {"title": "Democracy and Education", "authors": "John Dewey", "year": 1916, "venue": "Free Press", "level": 1, "desc": "杜威教育哲学，入门必学"},
                {"title": "How Children Learn", "authors": "John Holt", "year": 1964, "venue": "Penguin", "level": 2, "desc": "儿童学习理论"},
                {"title": "Mindset: The New Psychology of Success", "authors": "Carol Dweck", "year": 2006, "venue": "Random House", "level": 1, "desc": "成长型思维，教育心理学入门"},
                {"title": "The Reflective Practitioner", "authors": "Donald Schön", "year": 1983, "venue": "Basic Books", "level": 3, "desc": "反思性实践，教师教育"},
                {"title": "Experience and Education", "authors": "John Dewey", "year": 1938, "venue": "Kappa Delta Pi", "level": 1, "desc": "经验与教育，杜威教育思想入门"},
                {"title": "Pedagogy of the Oppressed", "authors": "Paulo Freire", "year": 1968, "venue": "Seabury Press", "level": 3, "desc": "被压迫者教育学，批判教育学奠基"},
                {"title": "School Effectiveness Research", "authors": "Creemers & Kyriakides", "year": 2008, "venue": "Routledge", "level": 3, "desc": "学校效能研究综述"},
                {"title": "Learning Theories & Instruction", "authors": "Schunk", "year": 2012, "venue": "Pearson", "level": 2, "desc": "学习理论与教学实践"},
                {"title": "How to Win Friends and Influence People", "authors": "Dale Carnegie", "year": 1936, "venue": "Simon & Schuster", "level": 1, "desc": "人性的弱点，人际沟通学习入门"},
                {"title": "The 7 Habits of Highly Effective People", "authors": "Stephen Covey", "year": 1989, "venue": "Free Press", "level": 1, "desc": "高效能人士七个习惯，自我管理学习入门"},
            ]
        },
        "art_design": {
            "name": "艺术设计",
            "videos": [
                # level 1
                {"title": "设计基础", "url": "https://www.icourse163.org/course/NEU-1001907001", "platform": "中国大学MOOC", "duration": "~20h", "level": 1},
                {"title": "UI/UX设计", "url": "https://www.coursera.org/specializations/ui-design", "platform": "Coursera", "duration": "~40h", "level": 2},
                {"title": "Adobe Photoshop教程", "url": "https://www.bilibili.com/video/BV1sb411e7cQ", "platform": "B站", "duration": "~30h", "level": 1},
                {"title": "三大构成(平面/色彩/立体)", "url": "https://www.bilibili.com/video/BV15J411x78q", "platform": "B站", "duration": "~60h", "level": 1},
                {"title": "平面设计", "url": "https://www.icourse163.org/course/SZU-1002016001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "色彩构成", "url": "https://www.icourse163.org/course/JLU-1002076001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "字体设计", "url": "https://www.icourse163.org/course/NEU-1002036001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "Adobe Illustrator 入门", "url": "https://www.bilibili.com/video/BV16s411S78X", "platform": "B站", "duration": "~25h", "level": 1},
                # level 2
                {"title": "品牌设计", "url": "https://www.icourse163.org/course/ZJU-1002086001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "交互设计", "url": "https://www.bilibili.com/video/BV1YJ411K7aS", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "Figma UI设计实战", "url": "https://www.bilibili.com/video/BV1kE421G7fA", "platform": "B站", "duration": "~25h", "level": 2},
                {"title": "设计心理学", "url": "https://www.icourse163.org/course/THU-1002046001", "platform": "中国大学MOOC", "duration": "~20h", "level": 2},
                {"title": "Adobe After Effects 动画", "url": "https://www.bilibili.com/video/BV1nJ411U79a", "platform": "B站", "duration": "~40h", "level": 3},
                {"title": "CalArts Graphic Design Specialization", "url": "https://www.coursera.org/specializations/graphic-design", "platform": "Coursera", "duration": "~50h", "level": 2},
                {"title": "网页设计入门", "url": "https://www.khanacademy.org/computing/computer-programming/html-css", "platform": "Khan Academy", "duration": "~15h", "level": 1},
                {"title": "产品设计手绘", "url": "https://www.bilibili.com/video/BV1nJ411G7gR", "platform": "B站", "duration": "~40h", "level": 2},
                # level 3
                {"title": "信息可视化设计", "url": "https://www.icourse163.org/course/TONGJI-1002086001", "platform": "中国大学MOOC", "duration": "~25h", "level": 3},
                {"title": "服务设计", "url": "https://www.icourse163.org/course/TONGJI-1002076001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "MIT Design Lab Advanced UX", "url": "https://ocw.mit.edu/courses/mas-s62-design-fundamentals-january-iap-2014/", "platform": "MIT OCW", "duration": "~20h", "level": 3},
                {"title": "Rhino 3D 产品建模", "url": "https://www.bilibili.com/video/BV1WE421a7Fp", "platform": "B站", "duration": "~40h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《设计心理学》", "author": "唐纳德·诺曼", "publisher": "中信出版社", "level": 1, "desc": "设计心理学经典"},
                {"title": "《写给大家看的设计书》", "author": "Robin Williams", "publisher": "人民邮电出版社", "level": 1, "desc": "设计入门经典"},
                {"title": "《配色设计原理》", "author": "伊达千代", "publisher": "中信出版社", "level": 1, "desc": "配色设计经典"},
                {"title": "《交互设计精髓》", "author": "Alan Cooper", "publisher": "电子工业出版社", "level": 2, "desc": "交互设计权威"},
                {"title": "《平面设计法则》", "author": "Timothy Samara", "publisher": "中国青年出版社", "level": 2, "desc": "平面设计规则与实践"},
                {"title": "《设计史》", "author": "Charlotte Fiell", "publisher": "Taschen", "level": 2, "desc": "现代设计史权威"},
                # level 2
                {"title": "《Logo设计圣经》", "author": "David Airey", "publisher": "人民邮电出版社", "level": 2, "desc": "Logo设计权威"},
                {"title": "《品牌设计法则》", "author": "Marty Neumeier", "publisher": "中信出版社", "level": 3, "desc": "品牌设计经典"},
                {"title": "《About Face 4:交互设计精髓》", "author": "Alan Cooper", "publisher": "电子工业出版社", "level": 3, "desc": "UX设计经典"},
                {"title": "《视觉传达设计》", "author": "钱永宁", "publisher": "上海交通大学出版社", "level": 2, "desc": "视觉设计教材"},
                {"title": "《IDEO 设计改变一切》", "author": "Tim Brown", "publisher": "万卷出版公司", "level": 2, "desc": "设计思维方法论"},
                {"title": "《Grid Systems in Graphic Design》", "author": "Josef Muller-Brockmann", "publisher": "Niggli", "level": 3, "desc": "栅格系统设计圣经"},
                # level 3
                {"title": "Designing Interactions", "authors": "Bill Moggridge", "publisher": "MIT Press", "level": 2, "desc": "交互设计经典"},
                {"title": "The Design of Everyday Things", "authors": "Donald Norman", "publisher": "Basic Books", "level": 2, "desc": "设计心理学奠基"},
                {"title": "《用户体验要素》", "author": "Jesse James Garrett", "publisher": "机械工业出版社", "level": 2, "desc": "UX五层模型经典"},
                {"title": "《Don't Make Me Think》", "author": "Steve Krug", "publisher": "New Riders", "level": 1, "desc": "Web可用性设计入门"},
            ],
            "papers": [
                {"title": "Designing Interactions", "authors": "Bill Moggridge", "year": 2007, "venue": "MIT Press", "level": 2, "desc": "交互设计经典"},
                {"title": "The Design of Everyday Things", "authors": "Donald Norman", "year": 1988, "venue": "Basic Books", "level": 1, "desc": "设计心理学奠基，设计入门必读"},
                {"title": "The Bauhaus: 1919-1933", "authors": "Walter Gropius", "year": 1925, "venue": "Bauhaus", "level": 2, "desc": "包豪斯现代设计开端"},
                {"title": "Notes on the Synthesis of Form", "authors": "Christopher Alexander", "year": 1964, "venue": "Harvard UP", "level": 3, "desc": "设计方法论开山"},
                {"title": "Interaction Design: A Manifesto", "authors": "Winograd/Flores", "year": 1986, "venue": "CHI", "level": 3, "desc": "交互设计宣言"},
                {"title": "Design Research Methods", "authors": "Brenda Laurel", "year": 2003, "venue": "MIT Press", "level": 3, "desc": "设计研究方法综述"},
                {"title": "Seminar on Theories of Media", "authors": "McLuhan", "year": 1964, "venue": "McGraw-Hill", "level": 2, "desc": "媒介即信息，设计媒介"},
                {"title": "Experiencing Architecture", "authors": "Steen Rasmussen", "year": 1959, "venue": "MIT Press", "level": 1, "desc": "建筑与设计体验入门"},
                {"title": "Don't Make Me Think (Krug)", "authors": "Steve Krug", "year": 2000, "venue": "New Riders", "level": 1, "desc": "Web可用性设计入门经典"},
                {"title": "The Non-Designer's Design Book", "authors": "Robin Williams", "year": 1988, "venue": "Peachpit", "level": 1, "desc": "写给大家看的设计书，入门必读"},
            ]
        },
        "architecture": {
            "name": "建筑学",
            "videos": [
                # level 1
                {"title": "建筑设计基础", "url": "https://www.icourse163.org/course/TJU-1002005001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "建筑初步", "url": "https://www.bilibili.com/video/BV1KJ411A7qY", "platform": "B站", "duration": "~50h", "level": 1},
                {"title": "建筑历史", "url": "https://www.icourse163.org/course/HUST-1002629001", "platform": "中国大学MOOC", "duration": "~20h", "level": 2},
                {"title": "外国建筑史", "url": "https://www.icourse163.org/course/THU-1002006001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "建筑构造", "url": "https://www.icourse163.org/course/TJU-1001955001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "建筑物理", "url": "https://www.icourse163.org/course/TJU-1002026001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "建筑结构", "url": "https://www.icourse163.org/course/HUST-1002638001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "AutoCAD 入门教程", "url": "https://www.bilibili.com/video/BV18s411977v", "platform": "B站", "duration": "~30h", "level": 1},
                # level 2
                {"title": "建筑设计原理", "url": "https://www.icourse163.org/course/XJTU-1002076001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "景观设计", "url": "https://www.icourse163.org/course/TJU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "SketchUp + V-Ray 渲染", "url": "https://www.bilibili.com/video/BV1GJ411x7gA", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "建筑力学", "url": "https://www.icourse163.org/course/TJU-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "城市规划原理", "url": "https://www.icourse163.org/course/TONGJI-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "MIT 4.605 Architecture History", "url": "https://ocw.mit.edu/courses/4-605-introduction-to-the-history-and-theory-of-architecture-spring-2013/", "platform": "MIT OCW", "duration": "~35h", "level": 3},
                {"title": "Revit 建筑信息建模(BIM)", "url": "https://www.bilibili.com/video/BV1nJ411U7hJ", "platform": "B站", "duration": "~40h", "level": 3},
                {"title": "建筑设计手绘", "url": "https://www.bilibili.com/video/BV1uJ411K7oZ", "platform": "B站", "duration": "~35h", "level": 1},
                # level 3
                {"title": "参数化设计(Rhino+Grasshopper)", "url": "https://www.bilibili.com/video/BV17J411A7x3", "platform": "B站", "duration": "~50h", "level": 3},
                {"title": "建筑节能设计", "url": "https://www.icourse163.org/course/HIT-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "城市设计", "url": "https://www.icourse163.org/course/TONGJI-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "Harvard GSD Design Theory", "url": "https://www.gsd.harvard.edu/", "platform": "Harvard GSD", "duration": "自定进度", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《建筑空间组合论》", "author": "彭一刚", "publisher": "中国建筑工业出版社", "level": 1, "desc": "建筑设计基础经典"},
                {"title": "《建筑：形式、空间和秩序》", "author": "Francis D.K. Ching", "publisher": "天津大学出版社", "level": 1, "desc": "程大金，建筑入门圣经"},
                {"title": "《中国建筑史》", "author": "梁思成", "publisher": "中国建筑工业出版社", "level": 2, "desc": "中国建筑史权威"},
                {"title": "《外国建筑史》", "author": "陈志华", "publisher": "中国建筑工业出版社", "level": 2, "desc": "外国建筑史经典"},
                {"title": "《建筑物理》", "author": "柳孝图", "publisher": "中国建筑工业出版社", "level": 2, "desc": "建筑物理经典"},
                {"title": "《建筑结构选型》", "author": "钱稼茹", "publisher": "清华大学出版社", "level": 2, "desc": "建筑结构权威"},
                # level 2
                {"title": "《建筑构造》", "author": "李必瑜/魏宏杨", "publisher": "中国建筑工业出版社", "level": 2, "desc": "构造标准教材"},
                {"title": "《景观设计学》", "author": "俞孔坚", "publisher": "中国建筑工业出版社", "level": 3, "desc": "景观设计经典"},
                {"title": "《走向新建筑》", "author": "勒·柯布西耶", "publisher": "江苏科学技术出版社", "level": 2, "desc": "现代建筑宣言柯布"},
                {"title": "《图解思考:建筑表现技法》", "author": "Paul Laseau", "publisher": "中国建筑工业出版社", "level": 2, "desc": "建筑思维与表达"},
                {"title": "《城市规划原理》", "author": "吴志强/李德华", "publisher": "中国建筑工业出版社", "level": 3, "desc": "城规经典教材"},
                {"title": "S,M,L,XL", "authors": "Rem Koolhaas", "publisher": "Monacelli Press", "level": 3, "desc": "库哈斯建筑理论巨著"},
                # level 3
                {"title": "Towards a New Architecture", "authors": "Le Corbusier", "publisher": "G. Crès", "level": 2, "desc": "现代建筑宣言，柯布西耶"},
                {"title": "The Architecture of the City", "authors": "Aldo Rossi", "publisher": "Einaudi", "level": 3, "desc": "城市建筑理论罗西"},
                {"title": "Complexity and Contradiction in Architecture", "authors": "Robert Venturi", "publisher": "MoMA", "level": 3, "desc": "后现代建筑宣言"},
                {"title": "Delirious New York", "authors": "Rem Koolhaas", "publisher": "Monacelli", "level": 3, "desc": "库哈斯纽约癫狂建筑"},
            ],
            "papers": [
                {"title": "Towards a New Architecture", "authors": "Le Corbusier", "year": 1923, "venue": "G. Crès", "level": 1, "desc": "现代建筑宣言，入门必读"},
                {"title": "The Architecture of the City", "authors": "Aldo Rossi", "year": 1966, "venue": "Einaudi", "level": 3, "desc": "城市建筑理论"},
                {"title": "Architecture of Truth (Cistercian)", "authors": "Le Corbusier", "year": 1957, "venue": "Editions de", "level": 3, "desc": "朗香教堂与模数系统"},
                {"title": "Invisible Cities", "authors": "Italo Calvino", "year": 1972, "venue": "Einaudi", "level": 1, "desc": "看不见的城市，建筑空间入门"},
                {"title": "A Pattern Language", "authors": "Christopher Alexander", "year": 1977, "venue": "Oxford UP", "level": 3, "desc": "建筑模式语言，模式设计"},
                {"title": "Life of Buildings & Their Forms", "authors": "Bernhard Rudolf", "year": 2005, "venue": "Birkhauser", "level": 3, "desc": "可持续建筑形态"},
                {"title": "Villes et Paysages", "authors": "Michel Corajoud", "year": 1994, "venue": "Brussels", "level": 3, "desc": "城市与景观设计"},
                {"title": "Five Points of Architecture", "authors": "Le Corbusier", "year": 1926, "venue": "L'Esprit Nouveau", "level": 2, "desc": "新建筑五点理论"},
                {"title": "Architecture: Form, Space & Order", "authors": "Francis Ching", "year": 1979, "venue": "Wiley", "level": 1, "desc": "建筑：形式空间秩序，入门经典"},
                {"title": "The Story of Western Architecture", "authors": "John Summerson", "year": 1983, "venue": "Thames & Hudson", "level": 1, "desc": "西方建筑史话，入门通俗"},
            ]
        },
        "literature": {
            "name": "文学",
            "videos": [
                # level 1
                {"title": "中国文学经典", "url": "https://www.icourse163.org/course/BFSU-1002036001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "西方文学经典", "url": "https://www.icourse163.org/course/XJTU-1002086001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "Crash Course Literature", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtOADQx0r7dQZOXV8V6I1PpQ", "platform": "YouTube", "duration": "~12h", "level": 1},
                {"title": "文学理论", "url": "https://www.icourse163.org/course/NJU-1002006001", "platform": "中国大学MOOC", "duration": "~20h", "level": 1},
                {"title": "古代汉语", "url": "https://www.icourse163.org/course/PKU-1001925001", "platform": "中国大学MOOC", "duration": "~40h", "level": 1},
                {"title": "现代汉语", "url": "https://www.icourse163.org/course/HUST-1002617001", "platform": "中国大学MOOC", "duration": "~35h", "level": 1},
                {"title": "中国文学史(袁行霈)", "url": "https://www.bilibili.com/video/BV1nV411W7fZ", "platform": "B站", "duration": "~80h", "level": 1},
                {"title": "《红楼梦》专题", "url": "https://www.icourse163.org/course/PKU-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                # level 2
                {"title": "比较文学", "url": "https://www.icourse163.org/course/NJU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "文学批评", "url": "https://www.icourse163.org/course/ZJU-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "鲁迅研究", "url": "https://www.bilibili.com/video/BV15t4y1r7yS", "platform": "B站", "duration": "~25h", "level": 3},
                {"title": "欧洲文学史", "url": "https://www.icourse163.org/course/THU-1002066001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "小说创作与鉴赏", "url": "https://www.icourse163.org/course/HUST-1002076001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "诗歌创作", "url": "https://www.bilibili.com/video/BV1zE421f73T", "platform": "B站", "duration": "~20h", "level": 2},
                {"title": "Oxford English Literature", "url": "https://www.conted.ox.ac.uk/", "platform": "Oxford", "duration": "~30h", "level": 3},
                {"title": "Yale Milton 弥尔顿专题", "url": "https://oyc.yale.edu/english/engl-220", "platform": "Yale OCW", "duration": "~25h", "level": 3},
                # level 3
                {"title": "文艺学专题", "url": "https://www.bilibili.com/video/BV1nL4y1g7L2", "platform": "B站", "duration": "~30h", "level": 3},
                {"title": "Yale Introduction to Theory of Literature", "url": "https://oyc.yale.edu/english/engl-300", "platform": "Yale OCW", "duration": "~25h", "level": 3},
                {"title": "西方文论史", "url": "https://www.icourse163.org/course/THU-1002086001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "Harvard Shakespeare Studies", "url": "https://canvas.harvard.edu/", "platform": "Harvard", "duration": "~30h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《中国文学史》", "author": "袁行霈", "publisher": "高等教育出版社", "level": 1, "desc": "中国文学史权威"},
                {"title": "《西方文学史》", "author": "朱维之", "publisher": "南开大学出版社", "level": 2, "desc": "西方文学史经典"},
                {"title": "《文学理论教程》", "author": "童庆炳", "publisher": "高等教育出版社", "level": 2, "desc": "文学理论基础"},
                {"title": "《古代汉语》", "author": "王力", "publisher": "中华书局", "level": 2, "desc": "古代汉语权威"},
                {"title": "《现代汉语》", "author": "黄伯荣/廖序东", "publisher": "高等教育出版社", "level": 2, "desc": "现代汉语经典"},
                {"title": "《文学批评原理》", "author": "王先霈", "publisher": "华中师范大学出版社", "level": 3, "desc": "文学批评权威"},
                # level 2
                {"title": "《中国现代文学史》(钱理群)", "author": "钱理群等", "publisher": "北京大学出版社", "level": 2, "desc": "现当代文学经典"},
                {"title": "The Norton Anthology of English Literature", "author": "Stephen Greenblatt", "publisher": "Norton", "level": 2, "desc": "诺顿英国文学选集"},
                {"title": "《美学散步》", "author": "宗白华", "publisher": "上海人民出版社", "level": 2, "desc": "中国美学经典"},
                {"title": "《谈美》", "author": "朱光潜", "publisher": "中华书局", "level": 1, "desc": "美学入门经典"},
                {"title": "Literary Theory: An Introduction", "author": "Terry Eagleton", "publisher": "U of M Press", "level": 3, "desc": "伊格尔顿文学理论导论"},
                {"title": "《小说面面观》", "author": "E.M. Forster", "publisher": "上海译文出版社", "level": 2, "desc": "小说理论经典"},
                # level 3
                {"title": "Poetics", "authors": "Aristotle", "publisher": "Ancient Greek", "level": 2, "desc": "西方文学理论奠基诗学"},
                {"title": "The Western Canon", "authors": "Harold Bloom", "publisher": "Harcourt Brace", "level": 3, "desc": "西方正典，布鲁姆经典"},
                {"title": "《管锥编》", "author": "钱锺书", "publisher": "中华书局", "level": 3, "desc": "钱锺书比较文学巨著"},
                {"title": "《七缀集》", "author": "钱锺书", "publisher": "上海古籍", "level": 3, "desc": "钱锺书文学比较研究"},
            ],
            "papers": [
                {"title": "Poetics", "authors": "Aristotle", "year": -350, "venue": "Ancient Greek", "level": 1, "desc": "西方文学理论奠基，入门必读"},
                {"title": "The Literature of the World", "authors": "Harold Bloom", "year": 2000, "venue": "HarperCollins", "level": 3, "desc": "世界文学经典"},
                {"title": "On Sublime (Longinus)", "authors": "Pseudo-Longinus", "year": 100, "venue": "Ancient Greek", "level": 3, "desc": "论崇高，古典美学"},
                {"title": "Biographia Literaria", "authors": "Samuel Coleridge", "year": 1817, "venue": "Rest Fenner", "level": 3, "desc": "柯勒律治文学传记"},
                {"title": "Critique of Judgement (Kant)", "authors": "Immanuel Kant", "year": 1790, "venue": "Berlin", "level": 3, "desc": "判断力批判美学部分"},
                {"title": "The Anxiety of Influence", "authors": "Harold Bloom", "year": 1973, "venue": "Oxford UP", "level": 3, "desc": "影响的焦虑，布鲁姆"},
                {"title": "The Death of the Author", "authors": "Roland Barthes", "year": 1967, "venue": "Aspen", "level": 2, "desc": "作者之死，巴特文论入门"},
                {"title": "What is an Author (Foucault)", "authors": "Michel Foucault", "year": 1969, "venue": "Bulletin SSF", "level": 3, "desc": "福柯作者功能论"},
                {"title": "How to Read Literature Like a Professor", "authors": "Thomas Foster", "year": 2003, "venue": "Harper", "level": 1, "desc": "如何欣赏文学，文学入门指南"},
                {"title": "The Art of Fiction (Henry James)", "authors": "Henry James", "year": 1884, "venue": "Longmans", "level": 1, "desc": "小说的艺术，文学创作入门"},
            ]
        },
        "geography": {
            "name": "地理学",
            "videos": [
                # level 1
                {"title": "自然地理学", "url": "https://www.icourse163.org/course/NJU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "人文地理学", "url": "https://www.icourse163.org/course/XJTU-1002096001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "GIS基础", "url": "https://www.icourse163.org/course/WHU-1002076001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "Crash Course Geography", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtNC5HfBnhY0d8WjD2gP0a5V", "platform": "YouTube", "duration": "~12h", "level": 1},
                {"title": "经济地理学", "url": "https://www.icourse163.org/course/ZJU-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "区域地理学", "url": "https://www.icourse163.org/course/NJU-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "气象气候学", "url": "https://www.icourse163.org/course/NJU-1002086001", "platform": "中国大学MOOC", "duration": "~35h", "level": 1},
                {"title": "地貌学", "url": "https://www.icourse163.org/course/PKU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                # level 2
                {"title": "遥感概论", "url": "https://www.icourse163.org/course/WHU-1002086001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "GIS空间分析", "url": "https://www.icourse163.org/course/XJTU-1002036001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                {"title": "城市地理学", "url": "https://www.icourse163.org/course/BNU-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "ESRI ArcGIS 入门", "url": "https://www.bilibili.com/video/BV1bE421y7cZ", "platform": "B站", "duration": "~30h", "level": 2},
                {"title": "旅游地理学", "url": "https://www.icourse163.org/course/SYSU-1002046001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "政治地理学", "url": "https://www.icourse163.org/course/RUC-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "MIT 12.001 Earth Environment", "url": "https://ocw.mit.edu/courses/12-001-earth-system-science-fall-2019/", "platform": "MIT OCW", "duration": "~35h", "level": 2},
                {"title": "水文学", "url": "https://www.icourse163.org/course/HHU-1002036001", "platform": "中国大学MOOC", "duration": "~35h", "level": 2},
                # level 3
                {"title": "土壤地理学", "url": "https://www.icourse163.org/course/NJAU-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "生态学(地理方向)", "url": "https://www.icourse163.org/course/BJFU-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "Stanford Earth System Science", "url": "https://see.stanford.edu/", "platform": "Stanford", "duration": "~30h", "level": 3},
                {"title": "卫星遥感应用", "url": "https://www.bilibili.com/video/BV1bJ411L75q", "platform": "B站", "duration": "~30h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《自然地理学》", "author": "伍光和", "publisher": "高等教育出版社", "level": 1, "desc": "自然地理学经典"},
                {"title": "《人文地理学》", "author": "赵荣", "publisher": "高等教育出版社", "level": 1, "desc": "人文地理学权威"},
                {"title": "《地理信息系统》", "author": "邬伦", "publisher": "科学出版社", "level": 1, "desc": "GIS基础"},
                {"title": "《经济地理学》", "author": "李小建", "publisher": "高等教育出版社", "level": 1, "desc": "经济地理学经典"},
                {"title": "《气象学与气候学》", "author": "周淑贞", "publisher": "高等教育出版社", "level": 1, "desc": "气候学经典入门"},
                {"title": "《地图学》", "author": "祝国瑞", "publisher": "武汉大学出版社", "level": 1, "desc": "地图学基础权威"},
                {"title": "《遥感导论》", "author": "梅安新", "publisher": "高等教育出版社", "level": 2, "desc": "遥感权威"},
                {"title": "《GIS空间分析》", "author": "王劲峰", "publisher": "科学出版社", "level": 2, "desc": "空间分析经典"},
                # level 2
                {"title": "《城市地理学》(许学强)", "author": "许学强/周一星", "publisher": "高等教育出版社", "level": 2, "desc": "城地经典教材"},
                {"title": "《区域分析与区域规划》", "author": "崔功豪", "publisher": "高等教育出版社", "level": 2, "desc": "区域研究经典"},
                {"title": "《地理学与地理学家》", "author": "R.J. Johnston", "publisher": "商务印书馆", "level": 3, "desc": "地理学史经典"},
                {"title": "《Spatial Analysis》", "author": "Cliff & Ord", "publisher": "Pion", "level": 3, "desc": "空间统计经典"},
                {"title": "Environmental Geoscience", "author": "Nelson", "publisher": "Brooks/Cole", "level": 2, "desc": "环境地球科学入门"},
                {"title": "《中国地理》", "author": "赵济", "publisher": "高等教育出版社", "level": 2, "desc": "中国区域地理权威"},
                # level 3
                {"title": "Geography and Politics", "authors": "Harold Mackinder", "publisher": "Geographical Journal", "level": 2, "desc": "地缘政治理论"},
                {"title": "The Spatial Organization", "authors": "Walter Christaller", "publisher": "Gustav Fischer", "level": 3, "desc": "中心地理论"},
                {"title": "《History of Cartography》", "author": "Leo Bagrow", "publisher": "Transaction", "level": 3, "desc": "地图学史巨著"},
                {"title": "The Geographic Mosaic of Evolution", "authors": "Thompson", "publisher": "U Chicago", "level": 3, "desc": "地理与进化生物学"},
            ],
            "papers": [
                {"title": "Geography and Politics", "authors": "Harold Mackinder", "year": 1904, "venue": "Geographical Journal", "level": 1, "desc": "地缘政治理论入门必读"},
                {"title": "The Spatial Organization", "authors": "Walter Christaller", "year": 1933, "venue": "Gustav Fischer", "level": 3, "desc": "中心地理论"},
                {"title": "Tragedy of the Commons", "authors": "Garrett Hardin", "year": 1968, "venue": "Science", "level": 1, "desc": "公地悲剧，环境地理入门"},
                {"title": "Global Warming Hansen", "authors": "James Hansen", "year": 1988, "venue": "JGR", "level": 3, "desc": "全球变暖科学奠基"},
                {"title": "Core-Periphery Model", "authors": "Krugman", "year": 1991, "venue": "JPE", "level": 3, "desc": "新经济地理学开端"},
                {"title": "Environmental Kuznets Curve", "authors": "Grossman & Krueger", "year": 1991, "venue": "QJE", "level": 2, "desc": "环境库兹涅茨曲线"},
                {"title": "Anthropocene Working Group", "authors": "Zalasiewicz", "year": 2019, "venue": "Nature", "level": 2, "desc": "人类世正式定义"},
                {"title": "Limits to Growth", "authors": "Meadows et al.", "year": 1972, "venue": "Universe Books", "level": 1, "desc": "增长的极限，罗马俱乐部"},
            ]
        },
        "philosophy": {
            "name": "哲学",
            "videos": [
                # level 1
                {"title": "哲学导论", "url": "https://www.icourse163.org/course/PKU-1002056001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "Crash Course Philosophy", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtNgK6MZucdYldNkMybYIHKR", "platform": "YouTube", "duration": "~12h", "level": 1},
                {"title": "西方哲学史", "url": "https://www.icourse163.org/course/ZJU-1002016001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "中国哲学史", "url": "https://www.icourse163.org/course/BFSU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "逻辑学", "url": "https://www.icourse163.org/course/NJU-1002026001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "伦理学", "url": "https://www.icourse163.org/course/ZJU-1002036001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "马克思主义哲学原理", "url": "https://www.bilibili.com/video/BV1k7411s77X", "platform": "B站", "duration": "~50h", "level": 1},
                {"title": "先秦诸子哲学", "url": "https://www.bilibili.com/video/BV1Vx411n7aA", "platform": "B站", "duration": "~30h", "level": 1},
                # level 2
                {"title": "美学", "url": "https://www.icourse163.org/course/PKU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "宗教学", "url": "https://www.icourse163.org/course/HZNU-1002056001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "政治哲学", "url": "https://www.icourse163.org/course/FDU-1002046001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "科技哲学", "url": "https://www.icourse163.org/course/THU-1002066001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "西方哲学原著选读", "url": "https://www.icourse163.org/course/THU-1002086001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "Yale Introduction to Philosophy", "url": "https://oyc.yale.edu/philosophy/phil-176", "platform": "Yale OCW", "duration": "~25h", "level": 2},
                {"title": "伦理学导论", "url": "https://www.icourse163.org/course/SHNU-1002066001", "platform": "中国大学MOOC", "duration": "~25h", "level": 2},
                {"title": "Yale Death 哲学死亡", "url": "https://oyc.yale.edu/philosophy/phil-176", "platform": "Yale OCW", "duration": "~26h", "level": 2},
                # level 3
                {"title": "分析哲学", "url": "https://www.bilibili.com/video/BV1nE411T7pA", "platform": "B站", "duration": "~35h", "level": 3},
                {"title": "现象学导论", "url": "https://www.bilibili.com/video/BV1zA41157pL", "platform": "B站", "duration": "~30h", "level": 3},
                {"title": "Oxford Philosophy of Mind", "url": "https://www.conted.ox.ac.uk/", "platform": "Oxford", "duration": "~25h", "level": 3},
                {"title": "心灵哲学", "url": "https://www.icourse163.org/course/RUC-1002076001", "platform": "中国大学MOOC", "duration": "~25h", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《西方哲学史》", "author": "罗素(Bertrand Russell)", "publisher": "商务印书馆", "level": 1, "desc": "西方哲学史经典"},
                {"title": "《中国哲学史》", "author": "冯友兰", "publisher": "华东师范大学出版社", "level": 2, "desc": "中国哲学史权威"},
                {"title": "《存在与时间》", "author": "海德格尔", "publisher": "三联书店", "level": 3, "desc": "存在主义经典"},
                {"title": "《逻辑学导论》", "author": "Irving Copi", "publisher": "中国人民大学出版社", "level": 2, "desc": "逻辑学权威"},
                {"title": "《伦理学原理》", "author": "摩尔", "publisher": "商务印书馆", "level": 3, "desc": "伦理学经典"},
                {"title": "《美学》", "author": "黑格尔", "publisher": "商务印书馆", "level": 3, "desc": "美学经典"},
                # level 2
                {"title": "《马克思主义哲学原理》", "author": "肖前", "publisher": "中国人民大学出版社", "level": 2, "desc": "马哲标准教材"},
                {"title": "《中国哲学简史》", "author": "冯友兰", "publisher": "北京大学出版社", "level": 1, "desc": "冯友兰简明中国哲学史"},
                {"title": "《尼各马可伦理学》", "author": "亚里士多德", "publisher": "商务印书馆", "level": 3, "desc": "亚里士多德伦理学经典"},
                {"title": "《纯粹理性批判》", "author": "康德", "publisher": "商务印书馆", "level": 3, "desc": "康德哲学巨著"},
                {"title": "A History of Western Philosophy", "author": "Bertrand Russell", "publisher": "Simon & Schuster", "level": 2, "desc": "罗素西方哲学史原版"},
                {"title": "《哲学导论》", "author": "张世英", "publisher": "北京大学出版社", "level": 2, "desc": "国内哲学入门"},
                # level 3
                {"title": "The Republic", "authors": "Plato", "publisher": "Ancient Greek", "level": 2, "desc": "西方哲学奠基理想国"},
                {"title": "Critique of Pure Reason", "authors": "Immanuel Kant", "publisher": "Hartknoch", "level": 3, "desc": "康德纯粹理性批判"},
                {"title": "《存在与虚无》", "author": "萨特(Sartre)", "publisher": "三联书店", "level": 3, "desc": "萨特存在主义哲学"},
                {"title": "《真理与方法》", "author": "伽达默尔", "publisher": "商务印书馆", "level": 3, "desc": "哲学诠释学经典"},
            ],
            "papers": [
                {"title": "The Republic", "authors": "Plato", "year": -380, "venue": "Ancient Greek", "level": 1, "desc": "西方哲学奠基，理想国入门必读"},
                {"title": "Critique of Pure Reason", "authors": "Immanuel Kant", "year": 1781, "venue": "Hartknoch", "level": 3, "desc": "康德哲学经典"},
                {"title": "Meditations on First Philosophy", "authors": "Descartes", "year": 1641, "venue": "Elzevier", "level": 1, "desc": "我思故我在，笛卡尔入门"},
                {"title": "Tractatus Logico-Philosophicus", "authors": "Wittgenstein", "year": 1922, "venue": "Routledge", "level": 3, "desc": "维特根斯坦早期逻辑哲学"},
                {"title": "Being and Time", "authors": "Martin Heidegger", "year": 1927, "venue": "Niemeyer", "level": 3, "desc": "海德格尔存在与时间"},
                {"title": "The Second Sex", "authors": "Simone de Beauvoir", "year": 1949, "venue": "Gallimard", "level": 3, "desc": "波伏娃第二性，女性哲学"},
                {"title": "Discipline and Punish", "authors": "Michel Foucault", "year": 1975, "venue": "Gallimard", "level": 3, "desc": "福柯规训与惩罚"},
                {"title": "On the Origin of Inequality", "authors": "Rousseau", "year": 1755, "venue": "Marc-Michel Rey", "level": 2, "desc": "卢梭论人类不平等起源"},
                {"title": "The Problems of Philosophy (Russell)", "authors": "Bertrand Russell", "year": 1912, "venue": "Oxford", "level": 1, "desc": "哲学问题，罗素通俗哲学入门"},
                {"title": "Sophie's World", "authors": "Jostein Gaarder", "year": 1991, "venue": "Aschehoug", "level": 1, "desc": "苏菲的世界，哲学史通俗入门"},
            ]
        },
        "management": {
            "name": "管理学",
            "videos": [
                # level 1
                {"title": "管理学原理", "url": "https://www.icourse163.org/course/HUST-1002626001", "platform": "中国大学MOOC", "duration": "~25h", "level": 1},
                {"title": "MBA核心课程", "url": "https://www.coursera.org/specializations/business-administration", "platform": "Coursera", "duration": "~60h", "level": 2},
                {"title": "组织行为学", "url": "https://www.icourse163.org/course/BJUT-1002582001", "platform": "中国大学MOOC", "duration": "~20h", "level": 2},
                {"title": "市场营销学", "url": "https://www.icourse163.org/course/TJU-1002006001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "人力资源管理", "url": "https://www.icourse163.org/course/HUST-1002627001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "运营管理", "url": "https://www.icourse163.org/course/ZJU-1002076001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "供应链管理", "url": "https://www.icourse163.org/course/SZU-1002086001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "Crash Course Business", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtN0gewNfojFjL9R-zb93182", "platform": "YouTube", "duration": "~15h", "level": 1},
                # level 2
                {"title": "战略管理", "url": "https://www.icourse163.org/course/NKU-1002046001", "platform": "中国大学MOOC", "duration": "~35h", "level": 3},
                {"title": "公司治理", "url": "https://www.icourse163.org/course/RUC-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 3},
                {"title": "管理经济学", "url": "https://www.icourse163.org/course/THU-1002076001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "会计学基础", "url": "https://www.icourse163.org/course/HIT-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "管理学(罗宾斯)", "url": "https://www.bilibili.com/video/BV1V7411y78g", "platform": "B站", "duration": "~45h", "level": 1},
                {"title": "创业管理", "url": "https://www.icourse163.org/course/THU-1002036001", "platform": "中国大学MOOC", "duration": "~30h", "level": 2},
                {"title": "管理学理论与实务", "url": "https://www.icourse163.org/course/JLU-1002066001", "platform": "中国大学MOOC", "duration": "~30h", "level": 1},
                {"title": "项目管理(PMP)", "url": "https://www.bilibili.com/video/BV1rV411F7K8", "platform": "B站", "duration": "~40h", "level": 2},
                # level 3
                {"title": "MIT 15.401 Finance Theory", "url": "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2017/", "platform": "MIT OCW", "duration": "~40h", "level": 3},
                {"title": "MIT Sloan Microeconomics", "url": "https://ocw.mit.edu/courses/14-01sc-principles-of-microeconomics-fall-2011/", "platform": "MIT OCW", "duration": "~40h", "level": 2},
                {"title": "Stanford CS183 创业课", "url": "https://startupclass.samaltman.com/", "platform": "Stanford", "duration": "~20h", "level": 3},
                {"title": "哈佛商学院战略案例课", "url": "https://www.hbs.edu/", "platform": "HBS", "duration": "自定进度", "level": 3},
            ],
            "books": [
                # level 1
                {"title": "《管理学》", "author": "罗宾斯(Robbins)", "publisher": "中国人民大学出版社", "level": 1, "desc": "管理学经典教材"},
                {"title": "《管理经济学》", "author": "彼得森(H. Craig Petersen)", "publisher": "中国人民大学出版社", "level": 2, "desc": "管理经济学权威"},
                {"title": "《竞争战略》", "author": "迈克尔·波特", "publisher": "机械工业出版社", "level": 2, "desc": "战略管理经典"},
                {"title": "《市场营销学》", "author": "菲利普·科特勒", "publisher": "中国人民大学出版社", "level": 2, "desc": "市场营销权威"},
                {"title": "《人力资源管理》", "author": "加里·德斯勒", "publisher": "中国人民大学出版社", "level": 2, "desc": "HR管理经典"},
                {"title": "《运营管理》", "author": "Chase/Shankar", "publisher": "机械工业出版社", "level": 3, "desc": "运营管理权威"},
                # level 2
                {"title": "《卓有成效的管理者》", "author": "彼得·德鲁克", "publisher": "机械工业出版社", "level": 2, "desc": "德鲁克管理学必读"},
                {"title": "《管理的实践》", "author": "彼得·德鲁克", "publisher": "机械工业出版社", "level": 2, "desc": "德鲁克开创之作"},
                {"title": "《公司战略》", "author": "迈克尔·波特", "publisher": "华夏出版社", "level": 3, "desc": "波特五力模型"},
                {"title": "《基业长青》", "author": "James Collins", "publisher": "中信出版社", "level": 2, "desc": "高瞻远瞩公司特性"},
                {"title": "《从优秀到卓越》", "author": "Jim Collins", "publisher": "中信出版社", "level": 2, "desc": "公司管理跃迁"},
                {"title": "《蓝海战略》", "author": "W.钱·金", "publisher": "商务印书馆", "level": 3, "desc": "竞争战略新思路"},
                # level 3
                {"title": "The Practice of Management", "authors": "Peter Drucker", "publisher": "HarperCollins", "level": 2, "desc": "管理学经典德鲁克"},
                {"title": "Competitive Strategy", "authors": "Michael Porter", "publisher": "Free Press", "level": 3, "desc": "竞争战略理论"},
                {"title": "The Innovator's Dilemma", "authors": "Clayton Christensen", "publisher": "Harper", "level": 3, "desc": "创新者的窘境"},
                {"title": "In Search of Excellence", "authors": "Peters/Waterman", "publisher": "Harper", "level": 2, "desc": "追求卓越管理经典"},
            ],
            "papers": [
                {"title": "The Practice of Management", "authors": "Peter Drucker", "year": 1954, "venue": "HarperCollins", "level": 1, "desc": "管理学经典，德鲁克入门必读"},
                {"title": "Competitive Strategy", "authors": "Michael Porter", "year": 1980, "venue": "Free Press", "level": 3, "desc": "竞争战略理论"},
                {"title": "The Nature of the Firm", "authors": "Ronald Coase", "year": 1937, "venue": "Economica", "level": 2, "desc": "企业的性质科斯，入门"},
                {"title": "The Innovator's Dilemma", "authors": "Clayton Christensen", "year": 1997, "venue": "Harper", "level": 2, "desc": "颠覆性创新，入门了解"},
                {"title": "Motivation and Personality", "authors": "Abraham Maslow", "year": 1954, "venue": "Harper", "level": 1, "desc": "需求层次理论，管理学入门"},
                {"title": "The Human Side of Enterprise", "authors": "Douglas McGregor", "year": 1960, "venue": "McGraw-Hill", "level": 1, "desc": "X-Y理论管理人性，入门必读"},
                {"title": "The Five Competitive Forces", "authors": "Michael Porter", "year": 1979, "venue": "HBR", "level": 2, "desc": "五力模型HBR论文"},
                {"title": "Markets and Hierarchies", "authors": "Oliver Williamson", "year": 1975, "venue": "Free Press", "level": 3, "desc": "交易成本经济学"},
                {"title": "The One Minute Manager", "authors": "Blanchard & Johnson", "year": 1982, "venue": "William Morrow", "level": 1, "desc": "一分钟经理人，通俗管理入门"},
                {"title": "Zero to One (Peter Thiel)", "authors": "Peter Thiel", "year": 2014, "venue": "Crown", "level": 1, "desc": "从0到1，创业管理入门"},
            ]
        }
    }

    # 预设学科key到资源库key的映射（覆盖全部SUBJECTS中的学科）
    SUBJECT_TO_RESOURCE = {
        "computer_science": "computer_science",
        "ai": "ai",
        "data_science": "data_science",
        "software_engineering": "computer_science",
        "electronic": "computer_science",
        "math": "math",
        "english": "english",
        "finance": "finance",
        "law": "law",
        "psychology": "psychology",
        "education": "education",
        "art_design": "art_design",
        "physics": "physics",
        "chemistry": "chemistry",
        "biology": "biology",
        "medicine": "medicine",
        "engineering": "engineering",
        "mechanical": "engineering",
        "civil": "engineering",
        "electrical": "engineering",
        "materials": "engineering",
        "environmental": "geography",
        "geography": "geography",
        "history": "history",
        "philosophy": "philosophy",
        "politics": "law",
        "economics": "economics",
        "management": "management",
        "marketing": "management",
        "accounting": "finance",
        "statistics": "data_science",
        "linguistics": "english",
        "literature": "literature",
        "music": "music",
        "sports": "biology",
        "agriculture": "biology",
        "architecture": "architecture",
        "design": "art_design",
        "media": "art_design",
        "journalism": "literature",
        "public_health": "medicine",
        "nursing": "medicine",
        "pharmacy": "medicine",
        "dentistry": "medicine",
        "veterinary": "medicine",
        "marine": "biology",
        "atmospheric": "geography",
        "geology": "geography",
        "astronomy": "physics",
        "optics": "physics",
        "robotics": "ai",
        "network": "computer_science",
        "database": "computer_science",
        "security": "computer_science",
        "multimedia": "art_design",
        "game": "art_design",
        "animation": "art_design",
        "film": "art_design",
    }

    def generate(self, context: dict) -> dict:
        subject = context.get("subject", "computer_science")
        subject_name = context.get("subject_name", subject)
        level = context.get("level", 1)
        topic = context.get("topic", subject_name)

        # 使用精确映射匹配资源库
        db_key = self._resolve_resource_db(subject)
        db = self.RESOURCE_DB.get(db_key, self.RESOURCE_DB["computer_science"])

        def filter_level(items, user_level):
            if user_level == 1:
                return [i for i in items if i["level"] == 1]
            elif user_level == 2:
                return [i for i in items if i["level"] == 2]
            elif user_level == 3:
                return [i for i in items if i["level"] in [2, 3]]
            elif user_level == 4:
                return [i for i in items if i["level"] == 3]
            else:
                return [i for i in items if i["level"] <= user_level]

        videos = filter_level(db["videos"], level)
        books = filter_level(db["books"], level)
        papers = filter_level(db.get("papers", []), level)

        # 兜底
        if not videos:
            videos = filter_level(self.RESOURCE_DB["computer_science"]["videos"], level)
        if not books:
            books = filter_level(self.RESOURCE_DB["computer_science"]["books"], level)

        return {
            "type": "multimedia",
            "title": f"推荐资源 · {topic} · {db['name']}",
            "format": "recommendation",
            "generated_at": datetime.utcnow().isoformat(),
            "videos": videos,
            "books": books,
            "papers": papers,
            "metadata": {
                "subject": subject,
                "level": level,
                "topic": topic,
                "discipline": db["name"],
                "total_items": len(videos) + len(books) + len(papers),
            }
        }

    def _resolve_resource_db(self, subject: str) -> str:
        """根据预设学科key精确匹配到资源库key，兜底走computer_science"""
        subject_lower = subject.strip().lower()

        # 1. 精确预设映射表
        if subject_lower in self.SUBJECT_TO_RESOURCE:
            return self.SUBJECT_TO_RESOURCE[subject_lower]

        # 2. 关键词匹配（兼容自定义输入）
        keyword_mapping = {
            "ai": ["ai", "ml", "machine learning", "deep learning", "artificial intelligence", "神经网络", "机器学习", "深度学习", "强化学习"],
            "python": ["python", "django", "flask", "fastapi"],
            "web": ["web", "html", "css", "javascript", "react", "vue", "node", "frontend", "backend", "全栈"],
            "data_science": ["data", "data analysis", "data science", "analytics", "统计分析", "数据", "pandas", "numpy", "sql"],
            "english": ["english", "英语", "ielts", "toefl", "gre", "sat", "linguistics", "language"],
            "math": ["math", "mathematics", "数学", "calculus", "algebra", "statistics", "linear algebra", "微积分", "线性代数", "概率论"],
            "physics": ["physics", "物理", "mechanics", "力学", "electromagnetism", "电磁学", "thermodynamics", "量子"],
            "computer_science": ["computer science", "计算机", "编程", "code", "software", "程序", "cs", "算法", "数据结构", "操作系统", "网络", "database", "security", "工程"],
        }
        for key, keywords in keyword_mapping.items():
            if any(kw in subject_lower for kw in keywords):
                return key

        return "computer_science"

    def find_resources(self, subject: str, level: int, topic: str = "") -> dict:
        """外部直接查询资源（供其他模块调用）"""
        return self.generate({"subject": subject, "level": level, "topic": topic or subject})


# ===== 新增：视频Agent（视频教程推荐 + AI视频生成） =====
class VideoAgent(ResourceRecommenderAgent):
    """视频Agent = 视频教程推荐 + AI智能视频生成

    继承自 ResourceRecommenderAgent，复用其视频资源库，
    并增加 AI视频生成能力（基于火山引擎豆包视频生成模型）。
    """
    name = "video"
    description = "视频教程推荐与AI智能视频生成"

    def generate(self, context: dict) -> dict:
        subject = context.get("subject", "computer_science")
        subject_name = context.get("subject_name", subject)
        level = context.get("level", 1)
        topic = context.get("topic", subject_name)

        # 复用父类的视频推荐逻辑
        db_key = self._resolve_resource_db(subject)
        db = self.RESOURCE_DB.get(db_key, self.RESOURCE_DB["computer_science"])

        def filter_level(items, user_level):
            if user_level == 1:
                return [i for i in items if i["level"] == 1]
            elif user_level == 2:
                return [i for i in items if i["level"] == 2]
            elif user_level == 3:
                return [i for i in items if i["level"] in [2, 3]]
            elif user_level == 4:
                return [i for i in items if i["level"] == 3]
            else:
                return [i for i in items if i["level"] <= user_level]

        videos = filter_level(db["videos"], level)
        if not videos:
            videos = filter_level(self.RESOURCE_DB["computer_science"]["videos"], level)

        # 生成AI视频脚本（用LLM，无需视频API密钥也能用）
        ai_video_script = self._generate_video_script(subject_name, topic, level, context)

        # 检查火山引擎视频API是否可用
        try:
            from llm_client import volc_video_enabled
            ai_video_enabled = volc_video_enabled()
        except Exception:
            ai_video_enabled = False

        return {
            "type": "video",
            "title": f"视频资源 · {topic} · {db['name']}",
            "format": "video_collection",
            "generated_at": datetime.utcnow().isoformat(),
            "videos": videos,
            "ai_video_script": ai_video_script,
            "ai_video_enabled": ai_video_enabled,
            "metadata": {
                "subject": subject,
                "level": level,
                "topic": topic,
                "discipline": db["name"],
                "total_videos": len(videos),
                "ai_video_ready": ai_video_enabled,
            }
        }

    def _generate_video_script(self, subject_name, topic, level, context):
        """用LLM生成AI视频脚本（视频的分镜、配音稿、字幕）"""
        level_names = {1: "入门", 2: "进阶", 3: "高级", 4: "专家"}
        level_name = level_names.get(level, "进阶")

        try:
            from utils import call_llm, call_llm_json
            sys_prompt = "你是一名视频教学脚本设计师，擅长将知识点转化为生动的视频分镜脚本。"
            user_prompt = (
                f"请为「{subject_name}」学科的「{topic}」主题设计一段5分钟教学视频的脚本。\n"
                f"目标观众：{level_name}水平学生\n\n"
                "请输出JSON：\n"
                '{"title": "视频标题", "duration": "5分钟", '
                '"scenes": [{"scene": 1, "visual": "画面描述", "narration": "配音内容", "duration": "30秒", "subtitle": "字幕内容"}], '
                '"summary": "视频整体总结"}\n'
                "只输出JSON，不要其他文字。"
            )
            parsed = call_llm_json(sys_prompt, user_prompt, agent_name='VideoScript')
            if parsed:
                parsed["generated_by"] = "llm"
                return parsed
        except Exception as e:
            print(f"[VideoAgent] 视频脚本LLM失败: {e}")

        # 兜底脚本模板
        return {
            "title": f"{topic} · {level_name}教学视频",
            "duration": "5分钟",
            "scenes": [
                {"scene": 1, "visual": f"开场画面：展示{topic}的核心概念图示", "narration": f"今天我们来学习{subject_name}中的{topic}。", "duration": "30秒", "subtitle": f"{topic}入门"},
                {"scene": 2, "visual": f"概念讲解：在屏幕上呈现{topic}的定义和核心要素", "narration": f"{topic}的核心思想可以概括为几个关键点……", "duration": "60秒", "subtitle": "核心概念"},
                {"scene": 3, "visual": f"示例演示：通过具体案例展示{topic}的应用", "narration": "我们通过一个具体例子来理解……", "duration": "120秒", "subtitle": "案例演示"},
                {"scene": 4, "visual": f"要点回顾：屏幕显示本节重点", "narration": "总结一下今天的内容……", "duration": "60秒", "subtitle": "要点回顾"},
                {"scene": 5, "visual": "结尾画面：预告下节内容", "narration": "下节课我们将继续深入探讨……", "duration": "30秒", "subtitle": "下节预告"},
            ],
            "summary": f"本视频系统讲解{topic}的核心概念、应用场景和学习要点，适合{level_name}水平学生。",
            "generated_by": "template"
        }


# ===== 新增：书籍论文Agent =====
class BookPaperAgent(ResourceRecommenderAgent):
    """书籍论文Agent = 推荐书籍 + 推荐论文

    继承自 ResourceRecommenderAgent，复用其资源库，
    只返回 books 和 papers 部分。
    """
    name = "book_paper"
    description = "推荐书籍与论文"

    def generate(self, context: dict) -> dict:
        subject = context.get("subject", "computer_science")
        subject_name = context.get("subject_name", subject)
        level = context.get("level", 1)
        topic = context.get("topic", subject_name)

        db_key = self._resolve_resource_db(subject)
        db = self.RESOURCE_DB.get(db_key, self.RESOURCE_DB["computer_science"])

        def filter_level(items, user_level):
            if user_level == 1:
                return [i for i in items if i["level"] == 1]
            elif user_level == 2:
                return [i for i in items if i["level"] == 2]
            elif user_level == 3:
                return [i for i in items if i["level"] in [2, 3]]
            elif user_level == 4:
                return [i for i in items if i["level"] == 3]
            else:
                return [i for i in items if i["level"] <= user_level]

        books = filter_level(db["books"], level)
        papers = filter_level(db.get("papers", []), level)

        if not books:
            books = filter_level(self.RESOURCE_DB["computer_science"]["books"], level)

        return {
            "type": "book_paper",
            "title": f"书籍论文推荐 · {topic} · {db['name']}",
            "format": "recommendation",
            "generated_at": datetime.utcnow().isoformat(),
            "books": books,
            "papers": papers,
            "metadata": {
                "subject": subject,
                "level": level,
                "topic": topic,
                "discipline": db["name"],
                "total_items": len(books) + len(papers),
            }
        }


# ===== Coordinator: 协调者智能体 =====
class GeneratorCoordinator:
    """
    资源生成协调者
    职责：
    1. 理解学生的资源需求
    2. 分解为具体任务，分发给各专业Agent（含TrapExamGenerator）
    3. 整合各Agent的输出
    4. 支持两种模式：按需单类型生成 / 全自动全套生成
    """

    def __init__(self):
        self.agents = {
            "document": DocAgent(),
            "mindmap": MindMapAgent(),
            "quiz": QuizAgent(),
            "case": CaseAgent(),
            "video": VideoAgent(),            # 视频教程 + AI智能视频生成
            "book_paper": BookPaperAgent(),   # 书籍 + 论文
            # 兼容旧接口：multimedia 仍可用（返回完整视频+书籍+论文）
            "multimedia": ResourceRecommenderAgent(),
            "trap_exam": TrapExamGenerator(),
        }

    def generate_all(self, context: dict) -> dict:
        """生成全套资源（6种类型全部生成）"""
        results = {}
        errors = []

        for agent_name, agent in self.agents.items():
            try:
                results[agent_name] = agent.generate(context)
            except Exception as e:
                errors.append({"agent": agent_name, "error": str(e)})

        return {
            "success": len(errors) == 0,
            "resources": results,
            "count": len(results),
            "errors": errors,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def generate_type(self, resource_type: str, context: dict) -> dict:
        """生成指定类型的资源"""
        agent = self.agents.get(resource_type)
        if not agent:
            return {"success": False, "error": f"未知资源类型: {resource_type}"}

        try:
            result = agent.generate(context)
            return {"success": True, "resource": result, "type": resource_type}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def parse_student_request(self, request_text: str) -> dict:
        """解析学生需求，提取生成上下文"""
        request_lower = request_text.lower()

        context = {
            "learning_goal": request_text,
            "weak_points": [],
            "topic": "",
            "question_count": 6,
        }

        topic_keywords = ["关于", "学习", "想学", "需要", "帮我", "生成"]
        for kw in topic_keywords:
            if kw in request_text:
                parts = request_text.split(kw, 1)
                if len(parts) > 1:
                    topic_hint = parts[1].strip()[:20]
                    context["topic"] = topic_hint
                    break

        if not context["topic"]:
            context["topic"] = request_text[:20]

        import re
        num_match = re.search(r'(\d+)\s*道', request_text)
        if num_match:
            context["question_count"] = min(20, int(num_match.group(1)))

        weak_patterns = ["不会", "不懂", "薄弱", "差", "弱", "难"]
        for wp in weak_patterns:
            if wp in request_lower:
                idx = request_lower.find(wp)
                context["weak_points"].append(request_text[max(0, idx-10):idx+20].strip())

        return context


# ===== 克星题生成Agent =====
class TrapExamGenerator(BaseGeneratorAgent):
    """克星题生成Agent - 针对学生认知弱点生成陷阱题目"""
    name = "trap_exam"
    description = "生成针对认知弱点的克星题"

    def generate(self, context: dict) -> dict:
        weak_points = context.get("weak_points", [])
        subject = context.get("subject", "computer_science")
        subject_name = context.get("subject_name", subject)
        profile = context.get("student_profile", {})

        if not weak_points:
            return {
                "type": "trap_exam",
                "title": f"【克星题】{subject_name}认知弱点专项训练",
                "format": "json",
                "generated_at": datetime.utcnow().isoformat(),
                "questions": [],
                "metadata": {
                    "subject": subject,
                    "weak_points_count": 0,
                    "total_questions": 0,
                    "profile_aware": profile.get("has_profile")
                }
            }

        # ===== 个性化画像感知调整 =====
        profile = context.get("student_profile", {})
        if profile.get("has_profile"):
            # 合并画像中的weak_points（中文描述），去重
            dim_scores = profile.get("dimension_scores", {})
            profile_weak_dims = profile.get("weak_points", [])
            cognitive_style = profile.get("cognitive_style", "综合型")
            
            # 将画像中的低分维度转成中文弱点描述
            for dim, score in dim_scores.items():
                if score < 35 and dim not in profile_weak_dims:
                    profile_weak_dims.append(dim)
            
            # 将维度名转为可读的中文弱点
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
            for dim in profile_weak_dims:
                desc = dim_to_weakness.get(dim, f"在{dim}方面需要加强")
                if desc not in weak_points:
                    weak_points.append(desc)

        return {
            "type": "trap_exam",
            "title": f"【克星题】{subject_name}认知弱点专项训练",
            "format": "json",
            "generated_at": datetime.utcnow().isoformat(),
            "questions": self._generate_trap_questions(subject_name, weak_points),
            "metadata": {
                "subject": subject,
                "weak_points_count": len(weak_points),
                "total_questions": min(5, len(weak_points)),
                "profile_aware": profile.get("has_profile")
            }
        }

    def _generate_trap_questions(self, subject_name, weak_points):
        questions = []
        count = min(5, len(weak_points))

        for i in range(count):
            weak_point = weak_points[i]
            q = self._make_trap_question(subject_name, weak_point, i + 1)
            questions.append(q)

        return questions

    def _make_trap_question(self, subject_name, weak_point, idx):
        """生成单个陷阱题目（LLM优先）"""
        try:
            from utils import call_llm, call_llm_json
            sys_prompt = "你是一个考试命题专家，擅长设计陷阱题来检测学生的认知盲区。"
            user_prompt = (
                f"学科：{subject_name}\n"
                f"针对弱点：{weak_point}\n"
                f"题目序号：{idx}/5\n\n"
                "请设计一道高质量选择题（4个选项）：\n"
                "1. 正确选项必须是该学科中的真实正确知识\n"
                "2. 干扰选项要精准对应学生的常见误解（针对上述弱点）\n"
                "3. 每一个干扰选项都要精心设计，让学生误以为是正确答案\n\n"
                '输出JSON ONLY，不要```json包裹：\n'
                '{"id": 1, "question": "题干", "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"], "answer": 0, "trap_explanation": "陷阱说明"}'
            )
            parsed = call_llm_json(sys_prompt, user_prompt, agent_name='TrapExam')
            if parsed:
                return parsed
        except Exception as e:
            print(f"[TrapExam] LLM失败: {e}")

        # --- 增强的回退陷阱题模板 ---
        trap_templates = [
            {"question": f"关于{subject_name}中的核心概念，以下哪项理解是最准确的？",
             "options": [
                 f"A. {subject_name}的核心概念建立在基本原理之上，需要通过系统学习逐步理解",
                 f"B. 只要记住{subject_name}的公式和定义就足够了",
                 f"C. {subject_name}中的概念都是独立存在的，彼此没有关联",
                 f"D. {subject_name}的概念无需理解，直接用就行"
             ], "answer": 0,
             "trap_explanation": f"本题针对[{weak_point}]设计。错误选项B、C、D分别对应三种典型误解："
                                f"只记不理解的机械学习、忽视概念间关联的碎片化思维、跳过理论直接实践的冒进倾向。"},
            {"question": f"在{subject_name}的学习过程中，以下哪种做法最有效？",
             "options": [
                 f"A. 在理解基础概念后，通过实际项目和练习来巩固和应用",
                 f"B. 只看视频教程，不动手实践",
                 f"C. 只做题不总结归纳",
                 f"D. 只学习不与他人讨论交流"
             ], "answer": 0,
             "trap_explanation": f"本题针对[{weak_point}]设计。A是最有效的学习方式——理论与实践结合。"
                                f"B、C、D都是常见但低效的学习习惯。"},
            {"question": f"当学习{subject_name}时遇到一个难以理解的概念，最佳策略是什么？",
             "options": [
                 f"A. 暂停当前内容，从不同角度查找资料、看示例、用类比理解",
                 f"B. 直接跳过，认为不重要",
                 f"C. 死记硬背定义",
                 f"D. 放弃学习这个主题"
             ], "answer": 0,
             "trap_explanation": f"本题针对[{weak_point}]设计。A体现了主动学习和批判性思维，"
                                f"是深度学习的关键能力。B、C、D都是常见的逃避策略。"},
            {"question": f"以下哪项是对{subject_name}中理论与实践关系的正确理解？",
             "options": [
                 f"A. 理论指导实践，实践检验理论，二者相辅相成",
                 f"B. 理论无用，只看实践",
                 f"C. 实践浪费时间的，只学理论就好",
                 f"D. 理论和实践是两条平行线，没有交集"
             ], "answer": 0,
             "trap_explanation": f"本题针对[{weak_point}]设计。理论与实践是相互促进的关系，"
                                f"错误选项反映了非此即彼的二元思维局限。"},
        ]

        template = trap_templates[idx % len(trap_templates)]
        return {"id": idx, **template}


# ===== 对话式画像构建Agent =====
class ProfileBuilderAgent:
    """
    对话式画像构建Agent（LLM驱动）
    通过自然语言对话，自动抽取8维画像

    核心改造：
    - LLM动态生成问题，根据用户回答自适应追问
    - 不再是固定6步问卷，而是真正的智能对话
    - LLM决定何时收集到足够信息，自动结束
    - 对话中自然判断用户水平，而非仅靠最后分析
    """

    # 保留旧阶段定义用于兼容降级
    STAGES = [
        "greeting",
        "basic_info",
        "knowledge_dim",
        "cognitive_dim",
        "practice_dim",
        "learning_dim",
        "summary",
        "complete",
    ]

    # LLM对话模式：最少问几轮，最多问几轮
    # 保持6个维度的问题不减少（专业、目标、知识水平、学习方式、实践频率、困难点）
    MIN_ROUNDS = 6
    MAX_ROUNDS = 8

    def __init__(self):
        self.stage_questions = {
            "greeting": {
                "question": "你好！我是智学领航的AI学习顾问 🤖\n\n很高兴为你服务！让我通过聊天了解一下你的学习情况，为你定制个性化学习方案。\n\n请告诉我你的**专业或学习领域**是什么？",
                "dimension": None, "field": "major"
            },
            "basic_info": {
                "question": "太棒了！🌟\n\n你希望通过学习达到什么**目标**？\n\n比如：\n- 想通过考试/考证\n- 想提升工作技能\n- 想系统学习打基础\n- 想深入某个细分领域",
                "dimension": None, "field": "goal"
            },
            "knowledge_dim": {
                "question": "明白了！👍\n\n请用一句话描述你现在对该领域知识的**掌握程度**？\n\n比如：\n- ✅「完全零基础，什么都不会」\n- ✅「学过一些，但理解不深」\n- ✅「基础扎实，想深入学习」\n- ✅「已经有一定实践经验」\n- ✅「接近专业水平」",
                "dimension": "knowledge", "field": "knowledge_level"
            },
            "cognitive_dim": {
                "question": "很好的了解！💡\n\n在学习新知识时，你更喜欢哪种**学习方式**？\n\n- 先系统学理论，再动手实践\n- 直接动手做项目，遇到问题再查资料\n- 看视频/听课跟着学\n- 阅读文档和书籍自学\n- 和他人讨论交流学习",
                "dimension": "cognitive_style", "field": "learning_style"
            },
            "practice_dim": {
                "question": "了解！🎯\n\n你平时会**动手实践**吗？频率如何？\n\n- 每天都会实践\n- 每周有固定实践时间\n- 偶尔做做练习\n- 很少实践，主要是学习理论\n- 几乎不实践",
                "dimension": "application", "field": "practice_freq"
            },
            "learning_dim": {
                "question": "好的！📚\n\n你觉得自己最容易在哪些方面遇到**困难**？\n（可以选多个）\n\n- 概念理解困难\n- 记不住知识点\n- 不会应用到实际\n- 缺乏学习动力和规划\n- 遇到问题不知道如何解决\n- 学习效率低，容易分心",
                "dimension": "weakness", "field": "difficulties"
            },
            "summary": {
                "question": "非常感谢你的耐心回答！😊\n\n我已经对你的学习情况有了基本了解，现在为你生成**个性化学习画像**...",
                "dimension": None, "field": "summary"
            }
        }

    # ===== LLM驱动的智能对话核心 =====

    def chat_with_llm(self, conversation: list, user_answer: str) -> dict:
        """LLM驱动的智能对话：根据对话历史生成下一个问题或完成画像

        Returns:
            {"action": "ask", "question": "...", "options": [...], "stage": "chatting"}
            {"action": "complete", "profile": {...}}
        """
        # 构建对话历史文本
        dialog_parts = []
        for c in conversation:
            if c.get("question"):
                dialog_parts.append(f"AI: {c['question']}")
            if c.get("answer"):
                dialog_parts.append(f"学生: {c['answer']}")
        dialog = "\n".join(dialog_parts[-12:])  # 最近6轮对话

        round_count = len([c for c in conversation if c.get("answer")])

        # 实时水平评估：基于对话内容分析学生水平
        level_assessment = self._assess_level_realtime(conversation, user_answer)

        # 第一轮（关于专业/学习领域）不提供选项，其他轮次提供选项
        provide_options = round_count >= 1

        try:
            from utils import call_llm, call_llm_json

            sys_prompt = (
                "你是一位资深的教育顾问和心理测量专家，正在通过自然对话评估学生的学习画像。\n"
                "你的任务是根据对话历史，决定是继续提问还是结束评估。\n\n"
                "评估维度（8维）：\n"
                "1. knowledge - 知识掌握度\n"
                "2. understanding - 理解深度\n"
                "3. application - 应用能力\n"
                "4. analysis - 分析评价能力\n"
                "5. creativity - 创新思维\n"
                "6. self_learning - 自主学习力\n"
                "7. pace - 学习节奏\n"
                "8. cognitive - 认知层次\n\n"
                "必须覆盖的6个话题维度（每个维度至少问1个问题，不能跳过）：\n"
                "1. 专业/学习领域（第1轮，自由输入，不提供选项）\n"
                "2. 学习目标（通过考试/提升技能/系统学习/深入领域等）\n"
                "3. 知识掌握程度（零基础/学过一些/基础扎实/有实践经验等）\n"
                "4. 学习方式偏好（理论先行/动手实践/看视频/阅读自学/讨论交流等）\n"
                "5. 实践频率（每天/每周/偶尔/很少等）\n"
                "6. 学习困难点（概念理解/记忆/应用/动力/效率等）\n\n"
                "规则：\n"
                f"- 已对话{round_count}轮，最少需{self.MIN_ROUNDS}轮（6个维度各1轮），最多{self.MAX_ROUNDS}轮\n"
                f"- 如果对话轮数 < {self.MIN_ROUNDS}，必须继续提问，不能结束\n"
                f"- 必须确保6个话题维度都已问过才能结束评估\n"
                f"- 如果对话轮数 >= {self.MIN_ROUNDS}且6个维度都已覆盖，可以结束\n"
                f"- 如果对话轮数 >= {self.MAX_ROUNDS}，必须结束\n"
                "- 问题要自然、口语化，像真人老师聊天\n"
                "- 根据学生的回答灵活追问，不要机械地按固定顺序问\n"
                "- 可以针对学生回答中的细节深入追问，探测真实水平\n"
                "- 问题要简短（1-3句话）\n"
                "- 根据学生水平调整问题难度：基础学生问概念性问题，高等学生问应用/分析性问题\n\n"
                f"- 重要：回答JSON中如果 action 是 ask，必须同时返回 options 数组，包含3-5个可选项供学生点击选择\n"
                f"- {'当前是第1轮（关于专业/学习领域），不需要选项' if not provide_options else '当前需要为问题提供选项'}\n"
                "- options 中的选项应该覆盖可能的回答，用简洁的短语（2-10字），不要用句子\n"
                "- options 也可以包含 '其他' 选项让学生自由输入\n\n"
                "输出JSON格式：\n"
                '继续提问: {"action": "ask", "question": "你的下一个问题", "options": ["选项A", "选项B", "选项C", "其他"], "reason": "为什么问这个", "detected_level": int}\n'
                '结束评估: {"action": "complete", "profile": {"dimension_scores": {"knowledge": int, ...8个维度}, "major": "", "goal": "", "cognitive_style": "", "weak_points": [], "strong_points": [], "level": int, "level_name": ""}}\n\n'
                "注意：\n"
                "- 维度分数要有明显差异（最高最低至少差20分），不要所有维度都给一样的高分或低分\n"
                "- cognitive_style可选：系统理论型/实践驱动型/视听学习型/阅读自学型/社交学习型/综合型\n"
                "- level: 1=基础, 2=中等, 3=高等, 4=大神\n"
                "- 根据对话内容真实评分，不要敷衍给高分\n"
                f"- 当前实时水平评估：{level_assessment['level_name']}（{level_assessment['confidence']}%置信度）"
            )

            user_prompt = (
                f"=== 对话历史 ===\n{dialog}\n\n"
                f"=== 学生最新回答 ===\n{user_answer}\n\n"
                f"=== 实时水平评估 ===\n"
                f"水平: {level_assessment['level_name']}\n"
                f"置信度: {level_assessment['confidence']}%\n"
                f"依据: {level_assessment['reason']}\n\n"
                f"请决定下一步：继续提问（带选项）还是结束评估生成画像？"
            )

            result = call_llm_json(sys_prompt, user_prompt, agent_name='ProfileBuilder')
            if not result:
                return self._fallback_ask(conversation, user_answer)

            if result.get("action") == "complete":
                profile = result.get("profile", {})
                # 验证并补全画像
                profile = self._validate_profile(profile, conversation)
                return {"action": "complete", "profile": profile}
            else:
                question = result.get("question", "").strip()
                if not question:
                    return self._fallback_ask(conversation, user_answer)

                # 提取选项
                options = result.get("options", [])
                if not provide_options:
                    options = []  # 第一轮不显示选项

                return {
                    "action": "ask",
                    "question": question,
                    "options": options,
                    "stage": "chatting",
                    "detected_level": result.get("detected_level", level_assessment['level'])
                }

        except Exception as e:
            print(f"[ProfileBuilder LLM] 对话失败: {e}")
            return self._fallback_ask(conversation, user_answer)

    def _assess_level_realtime(self, conversation: list, user_answer: str) -> dict:
        """实时评估学生水平（基于关键词和回答特征）"""
        text = user_answer.lower()
        all_text = " ".join([c.get("answer", "") for c in conversation if c.get("answer")]).lower()

        # 高级词汇/表达
        advanced_terms = ['优化', '架构', '设计模式', '算法复杂度', '性能调优', '分布式', '微服务',
                         '底层原理', '源码', '内核', '编译器', '形式化', '数学证明', '论文']
        intermediate_terms = ['框架', '库', 'API', '组件', '模块化', '调试', '测试', '部署',
                             '数据库', '缓存', '接口', 'REST', 'JSON', '异步']
        basic_terms = ['基础', '入门', '简单', '不太懂', '刚开始', '零基础', '初学者',
                      '概念', '语法', '变量', '循环', '函数', 'Hello World']

        advanced_score = sum(1 for t in advanced_terms if t in all_text)
        intermediate_score = sum(1 for t in intermediate_terms if t in all_text)
        basic_score = sum(1 for t in basic_terms if t in all_text)

        # 回答长度和结构分析
        avg_length = sum(len(c.get("answer", "")) for c in conversation if c.get("answer")) / max(1, len([c for c in conversation if c.get("answer")]))
        has_structure = '。' in user_answer and ('因为' in user_answer or '所以' in user_answer or '首先' in user_answer)
        has_examples = '比如' in user_answer or '例如' in user_answer or '像' in user_answer

        # 综合评分
        if advanced_score >= 2 or (avg_length > 100 and has_structure and has_examples):
            return {"level": 4, "level_name": "大神", "confidence": 75, "reason": "使用高级术语，回答结构化且有实例"}
        elif advanced_score >= 1 or intermediate_score >= 3 or (avg_length > 60 and has_structure):
            return {"level": 3, "level_name": "高等", "confidence": 70, "reason": "使用专业术语，回答较完整"}
        elif intermediate_score >= 1 or basic_score >= 2 or avg_length > 30:
            return {"level": 2, "level_name": "中等", "confidence": 65, "reason": "有一定基础表达"}
        else:
            return {"level": 1, "level_name": "基础", "confidence": 60, "reason": "回答较简短或表达基础"}

    def _fallback_ask(self, conversation: list, user_answer: str) -> dict:
        """LLM失败时的降级方案：用固定阶段流程（带选项）"""
        round_count = len([c for c in conversation if c.get("answer")])

        # 如果还没到最少轮数，用固定问题
        if round_count < self.MIN_ROUNDS:
            stages = ["greeting", "basic_info", "knowledge_dim", "cognitive_dim", "practice_dim", "learning_dim"]
            if round_count < len(stages):
                stage = stages[round_count]
                q_data = self.stage_questions.get(stage, {})
                question = q_data.get("question", "请继续描述你的学习情况")
                options = []
                # 第一轮（greeting）不提供选项，其他轮次提供
                if round_count >= 1:
                    options = self._get_fallback_options(stage)
                return {"action": "ask", "question": question, "options": options, "stage": stage}

        # 到了最少轮数，直接完成
        profile = self.analyze_profile(conversation)
        return {"action": "complete", "profile": profile}

    def _get_fallback_options(self, stage: str) -> list:
        """降级方案的固定选项"""
        stage_options = {
            "basic_info": ["通过考试/考证", "提升工作技能", "系统学习打基础", "深入某个细分领域", "其他"],
            "knowledge_dim": ["零基础", "学过一些但不深", "基础扎实想深入", "有实践经验", "接近专业水平"],
            "cognitive_dim": ["系统学理论再实践", "直接动手做项目", "看视频/听课", "阅读文档自学", "讨论交流"],
            "practice_dim": ["每天都实践", "每周固定时间", "偶尔做练习", "很少实践", "几乎不实践"],
            "learning_dim": ["概念理解困难", "记不住知识点", "不会应用", "缺乏动力规划", "解决问题困难", "学习效率低"],
        }
        return stage_options.get(stage, ["选项A", "选项B", "选项C", "其他"])

    def _validate_profile(self, profile: dict, conversation: list) -> dict:
        """验证并补全LLM返回的画像数据"""
        text_fields = self._extract_text_fields(conversation)

        # 补全缺失维度
        dim_scores = profile.get("dimension_scores", {})
        for dim_id in ["knowledge", "understanding", "application", "analysis",
                       "creativity", "self_learning", "pace", "cognitive"]:
            if dim_id not in dim_scores or not isinstance(dim_scores[dim_id], (int, float)):
                dim_scores[dim_id] = 50
            else:
                dim_scores[dim_id] = max(0, min(100, int(dim_scores[dim_id])))
        profile["dimension_scores"] = dim_scores

        # 检查分数是否过于均匀
        score_vals = list(dim_scores.values())
        if len(score_vals) >= 2 and (max(score_vals) - min(score_vals) < 15):
            rules_result = self._rules_analyze(conversation)
            profile["dimension_scores"] = rules_result.get("dimension_scores", dim_scores)

        # 补全文本字段
        for key in ["major", "goal", "cognitive_style"]:
            if not profile.get(key):
                profile[key] = text_fields.get(key, "")

        # 补全level
        if not profile.get("level"):
            scores = list(dim_scores.values())
            avg = sum(scores) / len(scores) if scores else 50
            if avg >= 85:
                profile["level"] = 4
                profile["level_name"] = "大神"
            elif avg >= 65:
                profile["level"] = 3
                profile["level_name"] = "高等"
            elif avg >= 40:
                profile["level"] = 2
                profile["level_name"] = "中等"
            else:
                profile["level"] = 1
                profile["level_name"] = "基础"

        # 补全weak/strong points
        if not isinstance(profile.get("weak_points"), list):
            profile["weak_points"] = text_fields.get("weak_points", [])
        if not isinstance(profile.get("strong_points"), list):
            profile["strong_points"] = text_fields.get("strong_points", [])

        profile.setdefault("practice_freq", text_fields.get("practice_freq", ""))
        profile.setdefault("difficulties", text_fields.get("difficulties", ""))

        return profile

    def get_question_for_stage(self, stage: str) -> dict:
        if stage not in self.STAGES:
            return {"stage": "complete", "question": "", "is_complete": True}
        last_idx = len(self.STAGES) - 1
        current_idx = self.STAGES.index(stage)
        if current_idx >= last_idx:
            return {"stage": "complete", "question": "", "is_complete": True}
        stage_info = self.stage_questions.get(stage, {})
        return {
            "stage": stage,
            "question": stage_info.get("question", ""),
            "field": stage_info.get("field"),
            "dimension": stage_info.get("dimension"),
            "is_complete": False
        }

    def get_next_stage(self, current_stage: str) -> str:
        try:
            current_idx = self.STAGES.index(current_stage)
        except ValueError:
            return self.STAGES[0] if self.STAGES else "complete"
        next_idx = current_idx + 1
        if next_idx >= len(self.STAGES):
            return "complete"
        return self.STAGES[next_idx]

    def analyze_profile(self, conversation: list) -> dict:
        """根据对话历史分析生成8维画像（LLM驱动）"""
        if not conversation:
            return self._default_profile()
        parts = []
        for c in conversation:
            parts.append("Q: " + c.get("question", ""))
            parts.append("A: " + c.get("answer", ""))
        dialog = "\n".join(parts)
        
        # 从对话中直接提取专业、目标等文本字段（LLM可能在输出中遗漏）
        text_fields = self._extract_text_fields(conversation)
        
        try:
            from utils import call_llm, call_llm_json
            sys_prompt = "你是一名教育心理学专家，分析学生对话，输出8维学习画像JSON。"
            user_prompt = (
                f"以下是与一位学生的教育访谈记录，请分析其学习画像：\n\n{dialog[:2000]}\n\n"
                "请从以下8个维度评分（0-100整数），**注意各维度分数应该明显差异**——\n"
                "一个学生不可能所有维度分数一样高或一样低，不同维度须体现真实差异：\n"
                "1. knowledge（知识掌握度）\n"
                "2. understanding（理解深度）\n"
                "3. application（应用能力）\n"
                "4. analysis（分析评价能力）\n"
                "5. creativity（创新思维）\n"
                "6. self_learning（自主学习力）\n"
                "7. pace（学习节奏）\n"
                "8. cognitive（认知层次）\n\n"
                "给分原则：每个维度独立评估，最高分和最低分之间至少有20分的差距才合理。\n"
                "同时给出：\n"
                "- major: 学生的专业/领域\n"
                "- goal: 学习目标\n"
                "- cognitive_style: 认知风格（系统理论型/实践驱动型/视听学习型/阅读自学型/社交学习型/综合型）\n"
                "- weak_points: 薄弱维度数组（分数明显偏低的维度id）\n"
                "- strong_points: 优势维度数组（分数明显偏高的维度id）\n"
                "- level: 综合水平等级（1-4整数）\n"
                "- level_name: 等级名称\n\n"
                "只输出JSON：{{\"dimension_scores\": {{...}}, \"major\": \"\", \"goal\": \"\", \"cognitive_style\": \"\", \"weak_points\": [], \"strong_points\": [], \"level\": int, \"level_name\": \"\"}}"
            )
            parsed = call_llm_json(sys_prompt, user_prompt, agent_name='ProfileBuilder')
            if parsed and isinstance(parsed.get("dimension_scores"), dict):
                returned = parsed
                # 检查LLM是否返回了过于均匀的分数（最高最低分差<15即判定为均匀）
                # 如果是，用规则引擎替换分数部分，保留LLM的文本字段
                llm_scores = returned.get("dimension_scores", {})
                score_vals = [v for v in llm_scores.values() if isinstance(v, (int, float))]
                scores_too_uniform = len(score_vals) >= 2 and (max(score_vals) - min(score_vals) < 15)
                
                if scores_too_uniform:
                    rules_result = self._rules_analyze(conversation)
                    returned["dimension_scores"] = rules_result.get("dimension_scores", llm_scores)
                    returned["weak_points"] = rules_result.get("weak_points", [])
                    returned["strong_points"] = rules_result.get("strong_points", [])
                    returned["level"] = rules_result.get("level", 2)
                    returned["level_name"] = rules_result.get("level_name", "中等")
                else:
                    if not returned.get("level"):
                        scores = returned["dimension_scores"].values()
                        avg_score = sum(scores) / len(scores) if scores else 50
                        if avg_score >= 85: returned["level"] = 4; returned["level_name"] = "大神"
                        elif avg_score >= 65: returned["level"] = 3; returned["level_name"] = "高等"
                        elif avg_score >= 40: returned["level"] = 2; returned["level_name"] = "中等"
                        else: returned["level"] = 1; returned["level_name"] = "基础"
                    if not isinstance(returned.get("weak_points"), list): returned["weak_points"] = []
                    if not isinstance(returned.get("strong_points"), list): returned["strong_points"] = []
                    returned.setdefault("practice_freq", "")
                    returned.setdefault("difficulties", "")
                # 后处理：用对话中直接提取的文本字段填补LLM遗漏
                for key in ["major", "goal", "cognitive_style"]:
                    if not returned.get(key):
                        returned[key] = text_fields.get(key, "")
                if not returned.get("weak_points") and text_fields.get("weak_points"):
                    returned["weak_points"] = text_fields["weak_points"]
                if not returned.get("strong_points") and text_fields.get("strong_points"):
                    returned["strong_points"] = text_fields["strong_points"]
                if not returned.get("practice_freq") and text_fields.get("practice_freq"):
                    returned["practice_freq"] = text_fields["practice_freq"]
                if not returned.get("difficulties") and text_fields.get("difficulties"):
                    returned["difficulties"] = text_fields["difficulties"]
                return returned
        except Exception as e:
            print(f"[ProfileBuilder] LLM分析失败，使用规则引擎: {e}")
        # LLM失败：走规则引擎，但用对话中提取的文本字段兜底
        result = self._rules_analyze(conversation)
        for key in ["major", "goal", "cognitive_style", "practice_freq", "difficulties"]:
            if not result.get(key):
                result[key] = text_fields.get(key, "")
        return result

    @staticmethod
    def _extract_text_fields(conversation) -> dict:
        """直接从对话中提取文本字段（不依赖LLM）"""
        stages_map = {"greeting": "major", "basic_info": "goal"}
        result = {"major": "", "goal": "", "cognitive_style": "", "practice_freq": "", "difficulties": "", "weak_points": [], "strong_points": []}
        for entry in conversation:
            stage = entry.get("stage", "")
            answer = entry.get("answer", "")
            key = stages_map.get(stage)
            if key:
                result[key] = answer
            if stage == "practice_dim":
                if "每天" in answer or "经常" in answer or "持续" in answer:
                    result["practice_freq"] = "高频"
                elif "每周" in answer or "固定" in answer or "定期" in answer:
                    result["practice_freq"] = "中高频"
                elif "偶尔" in answer or "有时候" in answer:
                    result["practice_freq"] = "低频"
                elif "很少" in answer or "几乎不" in answer or "从不" in answer:
                    result["practice_freq"] = "极少"
                else:
                    result["practice_freq"] = answer[:30]
            if stage == "learning_dim":
                result["difficulties"] = answer
                # 提取薄弱点（扩展关键词覆盖）
                if any(w in answer for w in ["概念理解", "概念", "抽象", "复杂", "理论", "原理"]):
                    result["weak_points"].append("understanding")
                if any(w in answer for w in ["记不住", "记忆", "遗忘", "忘记", "忘", "背", "基础", "公式"]):
                    result["weak_points"].append("knowledge")
                if any(w in answer for w in ["不会应用", "写不出", "不会写", "代码", "实现", "实操", "动手"]):
                    result["weak_points"].append("application")
                if any(w in answer for w in ["动力", "规划", "坚持", "自律", "自制", "懒", "执行力"]):
                    result["weak_points"].append("self_learning")
                if any(w in answer for w in ["分心", "拖延", "效率", "专注", "集中", "浮躁", "走神"]):
                    result["weak_points"].append("pace")
                if any(w in answer for w in ["问题", "解决", "调试", "思路", "方法", "逻辑", "分析"]):
                    result["weak_points"].append("analysis")
                if any(w in answer for w in ["焦虑", "压力", "迷茫", "紧张", "没信心"]):
                    result["weak_points"].append("cognitive")
                # 如果写了困难内容但所有关键词都没命中，做兜底推断
                if not result["weak_points"] and len(answer) > 4:
                    # 描述越长越可能涉及理解和应用
                    if len(answer) >= 20:
                        result["weak_points"].extend(["understanding", "application"])
                    else:
                        result["weak_points"].append("understanding")
            if stage == "cognitive_dim":
                if "阅读" in answer or "文档" in answer or "书籍" in answer or "论文" in answer:
                    result["cognitive_style"] = "阅读自学型"
                elif "实践" in answer or "动手" in answer or "项目" in answer:
                    result["cognitive_style"] = "实践驱动型"
                elif "视频" in answer or "听课" in answer:
                    result["cognitive_style"] = "视听学习型"
                elif "讨论" in answer or "交流" in answer:
                    result["cognitive_style"] = "社交学习型"
                elif "理论" in answer or "系统" in answer or "先学" in answer:
                    result["cognitive_style"] = "系统理论型"
                else:
                    result["cognitive_style"] = "综合型"
        result["weak_points"] = list(set(result["weak_points"]))
        return result

    def _default_profile(self):
        # 默认画像：使用自然梯度代替全部50，避免结论趋同
        return {
            "level": 1, "level_name": "基础",
            "dimension_scores": {
                "knowledge": 45,
                "understanding": 40,
                "application": 35,
                "analysis": 40,
                "creativity": 35,
                "self_learning": 50,
                "pace": 50,
                "cognitive": 40,
            },
            "major": "", "goal": "", "cognitive_style": "综合型",
            "practice_freq": "", "difficulties": "",
            "weak_points": ["application", "creativity"],
            "strong_points": ["self_learning", "pace"],
        }

    @staticmethod
    def _rules_analyze(conversation):
        """基于规则的画像分析（回退方案）——各维度基线差异化，避免结论趋同"""
        stages = ProfileBuilderAgent.STAGES
        responses = {stages[i]: msg.get("answer", "") for i, msg in enumerate(conversation) if i < len(stages)}
        
        # 各维度基线由知识掌握度的回答决定，而不是全部从50起跑
        kd = responses.get("knowledge_dim", "")
        if "零基础" in kd or "不会" in kd or "完全" in kd or "小白" in kd:
            base = 15
        elif "学过一些" in kd or "了解一点" in kd or "不太深" in kd or "入门" in kd:
            base = 40
        elif "基础扎实" in kd or "掌握良好" in kd or "很好" in kd or "熟练" in kd:
            base = 75
        elif "精通" in kd or "专业水平" in kd or "深入" in kd or "专家" in kd:
            base = 95
        else:
            base = 50

        # 基线围绕知识掌握度建立自然梯度：不同维度不是同一个数
        scores = {
            "knowledge": base,
            "understanding": max(10, base - 5 + (10 if "精通" in kd else 0)),
            "application": max(10, base - 10 + (20 if "实践" in kd else 0)),
            "analysis": max(10, base - 5),
            "creativity": max(10, base - 10),
            "self_learning": max(10, base + (5 if "学过" in kd else -5)),
            "pace": max(10, base - 5),
            "cognitive": max(10, base - 8 + (10 if "深入" in kd else 0)),
        }
        
        major = responses.get("greeting", "")
        goal = responses.get("basic_info", "")
        cd = responses.get("cognitive_dim", "")
        pd = responses.get("practice_dim", "")
        ld = responses.get("learning_dim", "")
        
        # 认知风格 -> 理解深度和学习方式（在基线之上叠加，不做覆盖）
        if "阅读" in cd or "文档" in cd or "书籍" in cd or "论文" in cd or "源码" in cd:
            scores["self_learning"] += 20
            scores["analysis"] += 15
            scores["understanding"] += 10
            cognitive_style = "阅读自学型"
        elif "实践" in cd or "动手" in cd or "项目" in cd or "编程" in cd:
            scores["application"] += 20
            scores["creativity"] += 15
            scores["analysis"] += 5
            cognitive_style = "实践驱动型"
        elif "视频" in cd or "听课" in cd or "看视频" in cd or "教程" in cd:
            scores["understanding"] += 5
            cognitive_style = "视听学习型"
        elif "讨论" in cd or "交流" in cd or "他人" in cd or "合作" in cd:
            scores["analysis"] += 10
            scores["creativity"] += 10
            scores["application"] += 5
            cognitive_style = "社交学习型"
        elif "理论" in cd or "系统" in cd or "先学" in cd or "原理" in cd:
            scores["understanding"] += 15
            scores["analysis"] += 10
            scores["self_learning"] += 10
            cognitive_style = "系统理论型"
        else:
            cognitive_style = "综合型"
        
        # 实践频率 -> 应用能力
        practice_freq = "未知"
        if "每天" in pd or "经常" in pd or "持续" in pd:
            scores["application"] += 15
            scores["knowledge"] += 5
            scores["understanding"] += 5
            practice_freq = "高频"
        elif "每周" in pd or "固定" in pd or "定期" in pd:
            scores["application"] += 10
            practice_freq = "中高频"
        elif "偶尔" in pd or "有时候" in pd:
            scores["application"] -= 5
            practice_freq = "低频"
        elif "很少" in pd or "几乎不" in pd or "从不" in pd:
            scores["application"] -= 15
            scores["understanding"] -= 5
            scores["creativity"] -= 5
            practice_freq = "极少"
        
        # 学习目标 -> 认知层次
        if "考试" in goal or "考证" in goal or "通过" in goal:
            scores["pace"] += 15
            scores["understanding"] += 10
            scores["knowledge"] += 5
            scores["cognitive"] = round(scores["knowledge"] * 0.5 + scores["understanding"] * 0.3 + 15)
        elif "技能" in goal or "工作" in goal or "实战" in goal:
            scores["application"] += 15
            scores["analysis"] += 10
            scores["creativity"] += 10
            scores["pace"] += 10
            scores["cognitive"] = round(scores["application"] * 0.4 + scores["analysis"] * 0.25 + 20)
        elif "基础" in goal or "入门" in goal or "系统学习" in goal:
            scores["understanding"] += 10
            scores["knowledge"] += 5
            scores["pace"] += 5
            scores["cognitive"] = round(scores["knowledge"] * 0.5 + scores["understanding"] * 0.3 + 10)
        elif "深入" in goal or "研究" in goal or "精通" in goal:
            scores["analysis"] += 15
            scores["creativity"] += 15
            scores["understanding"] += 10
            scores["pace"] += 10
            scores["cognitive"] = round(scores["analysis"] * 0.4 + scores["creativity"] * 0.35 + 25)
        
        # 困难分析 -> 薄弱点和学习节奏（扩展关键词覆盖）
        weak_points = []
        strong_points = []
        
        def _apply_penalty(dim, pct):
            """按当前分数比例扣减：高分段减得多，低分段减得少"""
            scores[dim] = int(scores[dim] * (1 - pct))

        if any(w in ld for w in ["概念理解", "概念", "抽象", "复杂", "理论", "原理", "深奥", "晦涩"]):
            _apply_penalty("understanding", 0.25)
            _apply_penalty("cognitive", 0.15)
            weak_points.append("understanding")
        if any(w in ld for w in ["记不住", "记忆", "遗忘", "忘记", "忘", "背", "基础", "公式", "记"]):
            _apply_penalty("knowledge", 0.2)
            _apply_penalty("self_learning", 0.15)
            weak_points.append("knowledge")
        if any(w in ld for w in ["不会应用", "应用", "使用", "写不出", "不会写", "代码", "实现", "实操", "动手", "落地"]):
            _apply_penalty("application", 0.25)
            _apply_penalty("creativity", 0.1)
            weak_points.append("application")
        if any(w in ld for w in ["动力", "规划", "坚持", "自律", "自制", "懒", "执行力", "主动性"]):
            _apply_penalty("self_learning", 0.3)
            _apply_penalty("pace", 0.15)
            weak_points.append("self_learning")
        if any(w in ld for w in ["问题", "解决", "调试", "思路", "方法", "逻辑", "分析", "拆解", "推理"]):
            _apply_penalty("analysis", 0.2)
            _apply_penalty("application", 0.08)
            weak_points.append("analysis")
        if any(w in ld for w in ["效率", "分心", "拖延", "专注", "集中", "浮躁", "走神", "控制"]):
            _apply_penalty("pace", 0.3)
            _apply_penalty("self_learning", 0.15)
            weak_points.append("pace")
        if any(w in ld for w in ["焦虑", "压力", "迷茫", "紧张", "没信心", "不安"]):
            _apply_penalty("cognitive", 0.15)
            _apply_penalty("pace", 0.12)
            weak_points.append("cognitive")
        if any(w in ld for w in ["时间", "忙", "工作", "上课", "没空"]):
            _apply_penalty("pace", 0.2)
            _apply_penalty("self_learning", 0.08)
            weak_points.append("pace")
        # 兜底：写了困难内容但无一命中关键词，根据困难描述长度和综合度做温和推断
        if not weak_points and ld and len(ld) > 4:
            if len(ld) >= 30:
                _apply_penalty("understanding", 0.15)
                _apply_penalty("application", 0.12)
                weak_points.extend(["understanding", "application"])
            else:
                _apply_penalty("understanding", 0.12)
                weak_points.append("understanding")
        
        # 零基础惩罚：如果知识掌握度很低，其他维度上限受约束
        if scores["knowledge"] <= 30:
            for dim in ["understanding", "analysis", "creativity"]:
                cap = scores["knowledge"] + 20
                if scores[dim] > cap:
                    scores[dim] = cap
        
        # 精通奖励
        if scores["knowledge"] >= 80:
            for dim in ["understanding", "analysis", "self_learning"]:
                if scores[dim] < 65:
                    scores[dim] = 65
        
        # 确保分数在0-100范围内
        for k in scores:
            scores[k] = max(10, min(95, round(scores[k])))
        
        # 根据分数确定等级
        avg_score = sum(scores.values()) / len(scores)
        if avg_score >= 85:
            level, level_name = 4, "大神"
        elif avg_score >= 65:
            level, level_name = 3, "高等"
        elif avg_score >= 40:
            level, level_name = 2, "中等"
        else:
            level, level_name = 1, "基础"
        
        # 确定优势维度
        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        strong_points = [k for k, v in sorted_scores[:3] if v >= 60]
        
        return {
            "level": level, "level_name": level_name,
            "dimension_scores": scores,
            "major": major, "goal": goal,
            "cognitive_style": cognitive_style,
            "practice_freq": practice_freq,
            "difficulties": ld,
            "weak_points": weak_points,
            "strong_points": strong_points,
        }


# ===== 全局实例 =====
trap_exam_generator = TrapExamGenerator()
generator_coordinator = GeneratorCoordinator()
profile_builder = ProfileBuilderAgent()
doc_agent = DocAgent()
quiz_agent = QuizAgent()
case_agent = CaseAgent()
multimedia_agent = ResourceRecommenderAgent()
video_agent = VideoAgent()
book_paper_agent = BookPaperAgent()
