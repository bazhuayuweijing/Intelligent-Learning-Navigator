"""
为所有49个学科生成MOCK_RESOURCES条目并注入mock_data.py
- 从generate_all_mock_data.py提取案例数据
- 生成基本docs/quizzes/mindmaps/trap_exams
- 写入MOCK_RESOURCES + MOCK_PROFILE_INDEX
"""
import sys, os

# 1. 加载案例数据
sys.path.insert(0, '/tmp')
exec(open('/tmp/_dict.py', encoding='utf-8').read())
CASE_TEMPLATES = templates  # 49 subjects × 5 cases, tuple format

# 2. 现有学科
EXISTING_KEYS = {'computer_science', 'python', 'ai', 'math', 'physics', 'english'}

# 学科中文名映射
SUBJECT_NAMES = {
    "data_science": "数据科学", "software_engineering": "软件工程", "electronic": "电子工程",
    "finance": "金融学", "law": "法学", "psychology": "心理学", "education": "教育学",
    "art_design": "艺术设计", "chemistry": "化学", "biology": "生物学", "medicine": "临床医学",
    "engineering": "工程力学", "mechanical": "机械工程", "civil": "土木工程", "electrical": "电气工程",
    "materials": "材料科学", "environmental": "环境科学", "geography": "地理学",
    "history": "历史学", "philosophy": "哲学", "politics": "政治学", "economics": "经济学",
    "management": "管理学", "marketing": "市场营销", "accounting": "会计学",
    "statistics": "统计学", "linguistics": "语言学", "literature": "文学", "music": "音乐学",
    "sports": "体育学", "agriculture": "农学", "architecture": "建筑学", "design": "设计学",
    "media": "传播学", "journalism": "新闻学", "public_health": "公共卫生",
    "nursing": "护理学", "pharmacy": "药学", "dentistry": "口腔医学", "veterinary": "兽医学",
    "marine": "海洋科学", "atmospheric": "大气科学", "geology": "地质学",
    "astronomy": "天文学", "optics": "光学工程", "robotics": "机器人学",
    "network": "计算机网络", "database": "数据库", "security": "信息安全",
}

# Supplementary config subjects
SUBJECT_NAMES2 = {
    "data_science": "数据科学", "software_engineering": "软件工程", "electronic": "电子工程",
    "finance": "金融学", "law": "法学", "psychology": "心理学", "education": "教育学",
    "art_design": "艺术设计", "chemistry": "化学", "biology": "生物学", "medicine": "临床医学",
    "engineering": "工程力学", "mechanical": "机械工程", "civil": "土木工程", "electrical": "电气工程",
    "materials": "材料科学", "environmental": "环境科学", "geography": "地理学",
    "history": "历史学", "philosophy": "哲学", "politics": "政治学", "economics": "经济学",
    "management": "管理学", "marketing": "市场营销", "accounting": "会计学",
    "statistics": "统计学", "linguistics": "语言学", "literature": "文学", "music": "音乐学",
    "sports": "体育学", "agriculture": "农学", "architecture": "建筑学", "design": "设计学",
    "media": "传播学", "journalism": "新闻学", "public_health": "公共卫生",
    "nursing": "护理学", "pharmacy": "药学", "dentistry": "口腔医学", "veterinary": "兽医学",
    "marine": "海洋科学", "atmospheric": "大气科学", "geology": "地质学",
    "astronomy": "天文学", "optics": "光学工程", "robotics": "机器人学",
    "network": "计算机网络", "database": "数据库", "security": "信息安全",
}

# 3. 转换工具函数
def tuple_to_case_dict(t):
    """将tuple(7元素)转为dict格式"""
    (title, topics, difficulty, description, knowledge_point, steps, code_hint) = t
    # Escape single quotes in dict values for Python format
    def q(s):
        if isinstance(s, str):
            return s.replace("'", "\\'").replace('\n', '\\n')
        if isinstance(s, list):
            return [q(x) for x in s]
        return s
    
    return {
        "title": q(title),
        "topics": [q(x) for x in topics],
        "difficulty": q(difficulty),
        "description": q(description),
        "knowledge_point": q(knowledge_point),
        "steps": [q(x) for x in steps],
        "code_hint": q(code_hint),
    }

def format_case_dict(d, indent=8):
    """Format case dict as Python source code"""
    i = ' ' * indent
    i2 = ' ' * (indent+4)
    
    def fmt_list(lst, inner_indent):
        ii = ' ' * inner_indent
        items = []
        for item in lst:
            items.append(f"{ii}{repr(item)}")
        return "[\n" + ",\n".join(items) + f"\n{' ' * (inner_indent-4)}]"
    
    lines = []
    lines.append(f"{i}{{")
    lines.append(f"{i2}\"title\": {repr(d['title'])},",)
    lines.append(f"{i2}\"topics\": {fmt_list(d['topics'], indent+12)},")
    lines.append(f"{i2}\"difficulty\": {repr(d['difficulty'])},",)
    lines.append(f"{i2}\"description\": {repr(d['description'])},",)
    lines.append(f"{i2}\"knowledge_point\": {repr(d['knowledge_point'])},",)
    lines.append(f"{i2}\"steps\": {fmt_list(d['steps'], indent+12)},")
    lines.append(f"{i2}\"code_hint\": {repr(d['code_hint'])},",)
    lines[-1] = lines[-1].rstrip(',')  # No trailing comma on last key
    lines.append(f"{i}}}")
    return '\n'.join(lines)

# 4. 生成基础资源数据
def gen_docs(subj_key, subj_name):
    """为学科生成2份文档"""
    name = SUBJECT_NAMES.get(subj_key, subj_name)
    docs = [
        {"title": f"{name}基础教程", "content": f"# {name}基础教程\n\n{name}是当代大学生需要掌握的核心知识领域之一。本教程将系统介绍{name}的基本概念、核心理论和实践方法，帮助学习者建立完整的知识体系。\n\n## 第一部分：基础知识\n\n{name}的基础知识包括基本概念、发展历程和核心原理。理解这些基础内容对于后续深入学习至关重要。\n\n## 第二部分：核心理论\n\n在掌握基础知识后，将深入学习{name}的核心理论框架和分析方法。\n\n## 第三部分：实践应用\n\n通过实操案例将理论与实际结合，培养解决实际问题的能力。"},
        {"title": f"{name}进阶专题", "content": f"# {name}进阶专题\n\n本专题面向有一定{name}基础的学习者，深入探讨前沿技术和高级应用。\n\n## 专题一：高级理论与方法\n\n## 专题二：前沿技术趋势\n\n## 专题三：跨学科交叉应用\n\n通过进阶学习，培养在{name}领域独立研究和创新的能力。"},
    ]
    return docs

def gen_mindmaps(subj_key, subj_name):
    """为学科生成1份思维导图"""
    name = SUBJECT_NAMES.get(subj_key, subj_name)
    return [
        {"title": f"{name}知识体系", "content": f"# {name}知识体系\n## 基础概念\n- 定义与范畴\n- 发展历史\n- 核心术语\n## 理论框架\n- 主要理论\n- 分析方法\n- 研究范式\n## 实践应用\n- 工具与方法\n- 典型案例\n- 行业实践\n## 前沿方向\n- 当前热点\n- 发展趋势\n- 跨学科融合"},
    ]

def gen_quizzes(subj_key, subj_name):
    """为学科生成5道题目"""
    name = SUBJECT_NAMES.get(subj_key, subj_name)
    return [
        {"question": f"{name}的核心研究对象是什么？", "type": "choice", "answer": "A", "options": ["A. 准确", "B. 选项B", "C. 选项C", "D. 选项D"]},
        {"question": f"在{name}中，理论构建的首要步骤是？", "type": "choice", "answer": "B", "options": ["A. 数据收集", "B. 问题定义", "C. 方法选择", "D. 结果验证"]},
        {"question": f"以下哪项不是{name}的主要研究方法？", "type": "choice", "answer": "C", "options": ["A. 实验法", "B. 观察法", "C. 直觉法", "D. 建模法"]},
        {"question": f"{name}中系统分析的基本步骤包括哪些？", "type": "fill", "answer": f"问题识别、数据收集、分析建模、验证评估"},
        {"question": f"{name}的实际应用价值主要体现在哪些方面？请举例说明。", "type": "short_answer", "answer": f"{name}的核心价值在于提供系统的分析框架和解决方案方法。"},
    ]

def gen_trap_exams(subj_key, subj_name):
    """为学科生成2道陷阱题"""
    name = SUBJECT_NAMES.get(subj_key, subj_name)
    return [
        {"question": f"在{name}实践中，经验比理论更重要。", "type": "judgment", "answer": "错误", "explanation": f"理论和实践在{name}中相辅相成，理论指导实践，实践验证理论，两者不可偏废。"},
        {"question": f"所有{name}问题都可以用单一方法解决。", "type": "judgment", "answer": "错误", "explanation": f"{name}问题具有多样性，需要根据具体情况选择合适的方法或组合多种方法解决。"},
    ]

def gen_multimedia(subj_key, subj_name):
    """为学科生成多媒体资源"""
    name = SUBJECT_NAMES.get(subj_key, subj_name)
    return [{"title": f"{name}概述视频", "url": f"https://example.com/{subj_key}_overview.mp4", "duration": "15:00"}]

# 5. 生成所有数据
NEW_ENTRIES = {}
for subj_key in sorted(CASE_TEMPLATES.keys()):
    if subj_key in EXISTING_KEYS:
        continue  # 跳过已有学科
    
    subj_name = subj_key
    cases = CASE_TEMPLATES[subj_key]
    case_dicts = [tuple_to_case_dict(c) for c in cases]
    docs = gen_docs(subj_key, subj_name)
    mindmaps = gen_mindmaps(subj_key, subj_name)
    quizzes = gen_quizzes(subj_key, subj_name)
    trap_exams = gen_trap_exams(subj_key, subj_name)
    multimedia = gen_multimedia(subj_key, subj_name)
    
    NEW_ENTRIES[subj_key] = {
        "cases": case_dicts,
        "docs": docs,
        "mindmaps": mindmaps,
        "quizzes": quizzes,
        "trap_exams": trap_exams,
        "multimedia": multimedia,
    }

print(f"Generated data for {len(NEW_ENTRIES)} new subjects")

# 6. 格式化成Python代码
def format_resource_list(items, indent=8):
    """Format a list of dicts"""
    if not items:
        return '[]'
    
    i = ' ' * indent
    parts = []
    parts.append('[\n')
    for item in items:
        parts.append(' ' * (indent+4))
        parts.append(repr(item))
        parts.append(',\n')
    parts.append(i + ']')
    return ''.join(parts)

def format_resource_list_friendly(items, indent=8):
    """Format resource list with printable strings instead of escaped"""
    if not items:
        return '[]'
    
    i = ' ' * indent
    i2 = ' ' * (indent+4)
    
    lines = ['[']
    for item in items:
        lines.append(f"{i2}{{")
        for k, v in item.items():
            if isinstance(v, str):
                lines.append(f"{i2}    \"{k}\": {repr(v)},")
            elif isinstance(v, list):
                lines.append(f"{i2}    \"{k}\": [")
                for x in v:
                    lines.append(f"{i2}        {repr(x)},")
                lines.append(f"{i2}    ],")
        # Remove trailing comma from last key
        last_line = lines[-1]
        if last_line.endswith(','):
            lines[-1] = last_line.rstrip(',')
        lines.append(f"{i2}}},")
    lines.append(i + ']')
    return '\n'.join(lines)

# 7. 生成完整文本
output_lines = []
for subj_key in sorted(NEW_ENTRIES.keys()):
    data = NEW_ENTRIES[subj_key]
    output_lines.append(f'    "{subj_key}": {{')
    
    # Cases
    output_lines.append(f'        "cases": [')
    for cd in data["cases"]:
        output_lines.append(format_case_dict(cd, 12) + ',')
    output_lines.append('        ],')
    
    # Docs
    output_lines.append(f'        "docs": [')
    for d in data["docs"]:
        output_lines.append(f'            {repr(d)},')
    output_lines.append('        ],')
    
    # Mindmaps
    output_lines.append(f'        "mindmaps": [')
    for m in data["mindmaps"]:
        output_lines.append(f'            {repr(m)},')
    output_lines.append('        ],')
    
    # Quizzes
    output_lines.append(f'        "quizzes": [')
    for q in data["quizzes"]:
        output_lines.append(f'            {repr(q)},')
    output_lines.append('        ],')
    
    # Trap exams
    output_lines.append(f'        "trap_exams": [')
    for t in data["trap_exams"]:
        output_lines.append(f'            {repr(t)},')
    output_lines.append('        ],')
    
    # Multimedia
    output_lines.append(f'        "multimedia": [')
    for m in data["multimedia"]:
        output_lines.append(f'            {repr(m)},')
    output_lines.append('        ],')
    
    # Remove trailing comma on last key
    # Fix: find last }, line and remove its comma
    last_idx = len(output_lines) - 1
    for i in range(len(output_lines)-1, 0, -1):
        if output_lines[i].strip() == '],':
            # This is the closing of multimedia, that's the last key
            # Remove comma from multimedia opening line
            for j in range(i, 0, -1):
                if '"multimedia"' in output_lines[j]:
                    output_lines[j] = output_lines[j].rstrip(',')
                    break
            break
    
    output_lines.append('    },\n')

# Combine into the resource block
resources_block = '\n'.join(output_lines)

# Also generate MOCK_PROFILE_INDEX entries
index_entries = []
for subj_key in sorted(NEW_ENTRIES.keys()):
    data = NEW_ENTRIES[subj_key]
    n_cases = len(data["cases"])
    n_docs = len(data["docs"])
    n_mindmaps = len(data["mindmaps"])
    n_quizzes = len(data["quizzes"])
    
    # Build index for each resource type
    def make_index_entry(count, level_tags_list):
        """Generate index dict entries"""
        entries = []
        for idx in range(count):
            level, tags = level_tags_list[idx % len(level_tags_list)]
            entries.append(f'{idx}: {{"level": {level}, "tags": {repr(tags)}}}')
        return ', '.join(entries)
    
    # Distribute levels: case0/2=2, case1/3=2, case4=3
    case_levels = [(2, ["实践驱动型", "阅读自学型"]), (2, ["实践驱动型"]),
                  (2, ["实践驱动型", "系统理论型"]), (2, ["实践驱动型", "视听学习型"]),
                  (3, ["系统理论型", "阅读自学型"])]
    
    # Simple index: all cases level 2, mixed tags
    case_idx = ', '.join(
        f'{i}: {{"level": {l}, "tags": {repr(t)}}}'
        for i, (l, t) in enumerate(case_levels)
    )
    doc_idx = f'0: {{"level": 2, "tags": ["系统理论型", "阅读自学型"]}}, 1: {{"level": 2, "tags": ["系统理论型"]}}'
    mm_idx = f'0: {{"level": 1, "tags": ["视听学习型"]}}'
    q_idx = ', '.join(
        f'{i}: {{"level": {1 if i%3==0 or i%3==2 else 2}, "tags": []}}'
        for i in range(n_quizzes)
    )
    
    index_entries.append(f'''    "{subj_key}": {{
        "docs": {{{doc_idx}}},
        "mindmaps": {{{mm_idx}}},
        "quizzes": {{{q_idx}}},
        "cases": {{{case_idx}}},
    }},''')

index_text = '\n'.join(index_entries)

# Write to files
with open('/tmp/_mock_additions.txt', 'w', encoding='utf-8') as f:
    f.write(resources_block)

with open('/tmp/_mock_index.txt', 'w', encoding='utf-8') as f:
    f.write(index_text)

print(f"Resources block: ~{len(resources_block)//1024}KB")
print(f"Index block: ~{len(index_text)//1024}KB")
print(f"Subjects: {len(NEW_ENTRIES)}")

