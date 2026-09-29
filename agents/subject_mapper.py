"""
subject_mapper.py - 自定义学科到预设学科的智能映射层

Phase 1 实现：
  精确匹配 → 关键词匹配 → 预设学科兜底

使用示例：
  from agents.subject_mapper import resolve_subject, resolve_subject_for_display
  preset_key = resolve_subject("量子物理")     # → "physics"
  display_name, preset_key = resolve_subject_for_display("量子物理")  
  # → ("量子物理", "physics")
"""

import re

# 关键词 → 预设学科key 映射表
# 每个预设学科有多个关键词变体，匹配到首个即停止
KEYWORD_MAP = {
    # 计算机科学
    "computer_science": [
        r"计算机", r"编程", r"程序", r"软件开发", r"python", r"java", r"c\+\+", r"c#", r"javascript",
        r"算法", r"数据结构", r"操作系统", r"编译", r"网络工程", r"软件工程",
        r"代码", r"开发", r"前端", r"后端", r"全栈", r"app", r"应用程序",
        r"coding", r"programming", r"software",
    ],
    # 人工智能
    "ai": [
        r"人工智能", r"ai", r"机器学习", r"深度学习", r"神经网络", r"nlp",
        r"自然语言", r"计算机视觉", r"强化学习", r"智能", r"模式识别",
        r"data\s*mining", r"machine\s*learning", r"deep\s*learning",
        r"transformer", r"gpt", r"大模型", r"llm",
    ],
    # 数据科学
    "data_science": [
        r"数据科学", r"数据分析", r"数据挖掘", r"大数据", r"sql", r"数据库",
        r"可视化", r"统计", r"bi", r"商业智能", r"data\s*science",
        r"etl", r"数据仓库", r"data\s*analysis",
    ],
    # 电子信息
    "electronic": [
        r"电子", r"电路", r"嵌入式", r"单片机", r"fpga", r"信号",
        r"通信", r"物联网", r"iot", r"传感", r"自动化",
    ],
    # 数学
    "math": [
        r"数学", r"微积分", r"线性代数", r"概率", r"统计", r"几何",
        r"离散数学", r"数论", r"运筹学", r"mathematics", r"math",
    ],
    # 英语
    "english": [
        r"英语", r"英文", r"雅思", r"托福", r"gre", r"考研英语",
        r"四六级", r"english", r"商务英语", r"口语",
    ],
    # 金融会计
    "finance": [
        r"金融", r"会计", r"财务", r"投资", r"经济", r"审计", r"税务",
        r"banking", r"finance", r"股票", r"基金",
    ],
    # 法学
    "law": [
        r"法学", r"法律", r"法考", r"司法", r"知识产权", r"宪法",
        r"民法", r"刑法", r"law", r"legislation",
    ],
    # 心理学
    "psychology": [
        r"心理学", r"心理", r"psychology", r"认知科学", r"行为",
        r"人格", r"社会心理", r"心理咨询",
    ],
    # 教育学
    "education": [
        r"教育学", r"教育", r"教学", r"课程", r"培训", r"education",
        r"pedagogy", r"师范",
    ],
    # 艺术设计
    "art_design": [
        r"艺术", r"设计", r"插画", r"平面设计", r"ui", r"ux",
        r"视觉", r"创意", r"色彩", r"art", r"design",
    ],
    # 物理学
    "physics": [
        r"物理", r"力学", r"电磁", r"量子", r"相对论", r"热力学",
        r"光学", r"physics", r"粒子物理", r"凝聚态",
    ],
    # 化学
    "chemistry": [
        r"化学", r"chemistry", r"有机|无机", r"分析化学",
        r"化工", r"化学工程", r"材料化学",
    ],
    # 生物学
    "biology": [
        r"生物", r"biology", r"生命科学", r"遗传", r"基因",
        r"细胞", r"微生物", r"生态",
    ],
    # 医学
    "medicine": [
        r"医学", r"临床", r"内科", r"外科", r"病理", r"药理",
        r"medicine", r"medical", r"诊断",
    ],
    # 工程学
    "engineering": [
        r"工程", r"engineer", r"机械", r"土木", r"建筑",
        r"材料", r"环境", r"交通",
    ],
    # 机械工程
    "mechanical": [
        r"机械", r"mechanical", r"机电", r"制造", r"数控",
        r"plc", r"自动化",
    ],
    # 环境科学
    "environmental": [
        r"环境", r"环保", r"生态", r"environmental", r"可持续发展",
    ],
    # 历史学
    "history": [
        r"历史", r"history", r"史学", r"考古", r"世界史", r"中国史",
    ],
    # 经济学
    "economics": [
        r"经济", r"economics", r"宏观", r"微观", r"计量",
    ],
    # 管理学
    "management": [
        r"管理", r"management", r"工商管理", r"企业管理", r"行政管理",
    ],
    # 市场营销
    "marketing": [
        r"营销", r"marketing", r"市场", r"品牌", r"广告", r"电商",
    ],
    # 天文学
    "astronomy": [
        r"天文", r"astronomy", r"宇宙", r"天体", r"航天",
    ],
    # 机器人学
    "robotics": [
        r"机器人", r"robotics", r"robot", r"自动化",
    ],
    # 多媒体
    "multimedia": [
        r"多媒体", r"视频", r"音频", r"动画", r"渲染", r"blender",
        r"multimedia", r"影视",
    ],
    # 游戏设计
    "game": [
        r"游戏", r"game", r"unity", r"unreal", r"游戏引擎",
    ],
}


def resolve_subject(subject_input):
    """
    将用户输入的学科映射到预设学科key。
    
    映射优先级：
    1. 精确匹配预设key（大小写不敏感）
    2. 精确匹配预设显示名（如"计算机科学"）
    3. 关键词模糊匹配
    4. 兜底：返回原始输入（可用于新建动态学科）
    
    返回：预设学科key (str)
    
    示例：
      resolve_subject("计算机科学")     → "computer_science"
      resolve_subject("量子物理")       → "physics"
      resolve_subject("unknown_xyz")   → "unknown_xyz"（兜底）
    """
    from config import SUBJECTS
    s = subject_input.strip().lower() if subject_input else ""
    if not s:
        return "computer_science"  # 默认

    # 1. 精确匹配预设key
    for key in SUBJECTS:
        if s == key.lower() or s == key:
            return key

    # 2. 精确匹配预设显示名
    for key, name in SUBJECTS.items():
        if name and s == name.lower().strip():
            return key

    # 3. 关键词匹配
    matched = _keyword_match(s)
    if matched:
        return matched

    # 4. 兜底
    return subject_input.strip() if subject_input else "computer_science"


def resolve_subject_for_display(subject_input):
    """
    返回 (显示名, 预设key) 元组。
    用于前端展示时保留原始输入的名称。
    """
    from config import SUBJECTS
    raw = subject_input.strip() if subject_input else ""
    if not raw:
        return "计算机科学", "computer_science"
    
    preset_key = resolve_subject(raw)
    
    # 如果是预设学科，用预设显示名
    if preset_key in SUBJECTS:
        return SUBJECTS[preset_key], preset_key
    else:
        # 自定义学科：显示原始输入
        return raw, preset_key


def _keyword_match(text):
    """关键词模糊匹配"""
    for key, patterns in KEYWORD_MAP.items():
        for pat in patterns:
            # 中文关键词直接包含匹配
            if re.search(pat, text, re.IGNORECASE):
                return key
    return None


def add_subject_mapping(subject_key, keywords):
    """
    运行时添加新的关键词映射（方便后续配置化扩展）
    
    参数：
      subject_key: 预设学科key（须在SUBJECTS中存在）
      keywords: 关键词列表
    """
    if subject_key in KEYWORD_MAP:
        KEYWORD_MAP[subject_key].extend(keywords)
    else:
        KEYWORD_MAP[subject_key] = keywords
