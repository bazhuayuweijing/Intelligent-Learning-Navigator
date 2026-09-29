"""
学习资源推荐引擎
根据学校层级和学科方向，推荐匹配的学习资源
"""
import re
from urllib.parse import quote

# === 学校层级 ===
SCHOOL_TIERS = {
    "985":  {"label": "985 高校", "tone": "学术前沿型，推荐科研论文、顶会课程、前沿技术"},
    "211":  {"label": "211 高校", "tone": "专业进阶型，推荐精品MOOC、经典教材、项目实战"},
    "双一流": {"label": "双一流高校", "tone": "学科创新型，推荐学科特色课程、竞赛项目"},
    "普通本科": {"label": "普通本科", "tone": "实用技能型，推荐就业导向课程、考证资料、实训平台"},
    "专科": {"label": "专科/高职", "tone": "实操技能型，推荐职业技能证书、实训项目、工具教程"},
}

# === 学科关键词映射 ===
KEYWORD_MAP = {
    "计算机科学": ["计算机", "编程", "代码", "软件开发", "程序", "CS", "前端", "后端", "全栈"],
    "人工智能": ["人工智能", "AI", "机器学习", "深度学习", "神经网络", "大模型", "NLP", "自然语言", "CV", "计算机视觉", "LLM", "transformer", "GPT", "强化学习"],
    "数据科学": ["数据", "大数据", "数据分析", "数据挖掘", "SQL", "可视化", "ETL", "hadoop", "spark"],
    "软件工程": ["软件工程", "架构", "设计模式", "DevOps", "CI/CD", "敏捷", "微服务", "Docker", "K8s"],
    "电子信息": ["电子", "通信", "嵌入式", "物联网", "信号", "FPGA", "单片机", "电路"],
    "经济管理": ["经济", "管理", "营销", "MBA", "财务", "人力资源", "供应链"],
    "金融会计": ["金融", "会计", "CPA", "CFA", "投资", "银行", "证券", "基金"],
    "法学": ["法律", "法考", "民法", "刑法", "宪法", "知识产权", "律师"],
    "医学": ["医学", "临床", "护理", "药学", "中医", "解剖", "生理"],
    "数学": ["数学", "高数", "线性代数", "概率论", "统计学", "离散数学", "数学建模"],
    "英语": ["英语", "四六级", "雅思", "托福", "GRE", "翻译", "口语", "单词"],
    "心理学": ["心理", "认知", "行为", "咨询", "发展心理"],
    "教育学": ["教育", "教资", "师范", "课程设计", "教学法"],
    "艺术设计": ["设计", "UI", "UX", "平面", "插画", "摄影", "视频剪辑", "PS", "PR"],
}

# === 资源库 ===
RESOURCE_DB = {
    "计算机科学": [
        {"type": "课程", "name": "CS50: 计算机科学导论", "source": "Harvard/edX", "level": "入门"},
        {"type": "课程", "name": "数据结构与算法", "source": "浙江大学MOOC", "level": "核心"},
        {"type": "书籍", "name": "深入理解计算机系统(CSAPP)", "source": "机械工业出版社", "level": "经典"},
        {"type": "平台", "name": "LeetCode刷题", "source": "LeetCode.cn", "level": "实战"},
        {"type": "课程", "name": "操作系统", "source": "清华大学MOOC", "level": "核心"},
        {"type": "书籍", "name": "计算机网络：自顶向下方法", "source": "机械工业出版社", "level": "经典"},
    ],
    "人工智能": [
        {"type": "课程", "name": "机器学习 (Andrew Ng)", "source": "Stanford/Coursera", "level": "入门"},
        {"type": "课程", "name": "深度学习专项课程", "source": "deeplearning.ai", "level": "进阶"},
        {"type": "书籍", "name": "深度学习(花书)", "source": "MIT Press", "level": "经典"},
        {"type": "书籍", "name": "动手学深度学习(D2L)", "source": "开源/Amazon", "level": "实战"},
        {"type": "框架", "name": "PyTorch官方教程", "source": "pytorch.org", "level": "实战"},
        {"type": "竞赛", "name": "Kaggle竞赛", "source": "kaggle.com", "level": "实战"},
        {"type": "论文", "name": "Attention Is All You Need", "source": "NeurIPS 2017", "level": "经典"},
        {"type": "课程", "name": "李宏毅机器学习", "source": "国立台湾大学/YouTube", "level": "入门"},
    ],
    "数据科学": [
        {"type": "书籍", "name": "利用Python进行数据分析", "source": "O'Reilly", "level": "实战"},
        {"type": "课程", "name": "数据科学导论", "source": "Coursera", "level": "入门"},
        {"type": "工具", "name": "Pandas官方文档", "source": "pandas.pydata.org", "level": "实战"},
        {"type": "竞赛", "name": "天池大数据竞赛", "source": "阿里云天池", "level": "实战"},
    ],
    "软件工程": [
        {"type": "书籍", "name": "设计模式", "source": "机械工业出版社", "level": "经典"},
        {"type": "书籍", "name": "代码整洁之道", "source": "人民邮电出版社", "level": "进阶"},
        {"type": "课程", "name": "软件工程", "source": "北京大学MOOC", "level": "核心"},
        {"type": "工具", "name": "Git & GitHub", "source": "GitHub Docs", "level": "入门"},
    ],
    "电子信息": [
        {"type": "课程", "name": "信号与系统", "source": "西安电子科技大学MOOC", "level": "核心"},
        {"type": "书籍", "name": "模拟电子技术基础", "source": "高等教育出版社", "level": "经典"},
        {"type": "项目", "name": "Arduino开源硬件", "source": "arduino.cc", "level": "实战"},
    ],
    "经济管理": [
        {"type": "课程", "name": "经济学原理", "source": "北京大学MOOC", "level": "入门"},
        {"type": "书籍", "name": "管理学(罗宾斯)", "source": "中国人民大学出版社", "level": "经典"},
    ],
    "金融会计": [
        {"type": "书籍", "name": "公司理财(罗斯)", "source": "机械工业出版社", "level": "经典"},
        {"type": "证书", "name": "CPA注册会计师", "source": "中国注册会计师协会", "level": "考证"},
        {"type": "课程", "name": "金融学", "source": "中央财经大学MOOC", "level": "核心"},
    ],
    "法学": [
        {"type": "书籍", "name": "民法典理解与适用", "source": "人民法院出版社", "level": "经典"},
        {"type": "证书", "name": "法考备考资料", "source": "司法部", "level": "考证"},
    ],
    "数学": [
        {"type": "书籍", "name": "高等数学(同济版)", "source": "高等教育出版社", "level": "经典"},
        {"type": "课程", "name": "线性代数(MIT 18.06)", "source": "MIT OCW", "level": "经典"},
        {"type": "竞赛", "name": "全国大学生数学建模竞赛", "source": "CUMCM", "level": "竞赛"},
    ],
    "英语": [
        {"type": "考试", "name": "CET-4/6 真题", "source": "星火英语", "level": "考证"},
        {"type": "考试", "name": "雅思IELTS", "source": "剑桥雅思", "level": "进阶"},
        {"type": "APP", "name": "墨墨背单词", "source": "App Store", "level": "入门"},
    ],
    "心理学": [
        {"type": "书籍", "name": "心理学与生活(第19版)", "source": "人民邮电出版社", "level": "入门"},
        {"type": "课程", "name": "普通心理学", "source": "北京师范大学MOOC", "level": "核心"},
    ],
    "教育学": [
        {"type": "证书", "name": "教师资格证备考", "source": "教育部", "level": "考证"},
        {"type": "书籍", "name": "教育学基础", "source": "教育科学出版社", "level": "经典"},
    ],
    "艺术设计": [
        {"type": "课程", "name": "平面设计基础", "source": "中国美术学院MOOC", "level": "入门"},
        {"type": "工具", "name": "Figma教程", "source": "figma.com", "level": "实战"},
        {"type": "书籍", "name": "写给大家看的设计书", "source": "人民邮电出版社", "level": "入门"},
    ],
}

DEFAULT_RESOURCES = [
    {"type": "平台", "name": "中国大学MOOC", "source": "icourse163.org", "level": "通用"},
    {"type": "平台", "name": "学堂在线", "source": "xuetangx.com", "level": "通用"},
    {"type": "平台", "name": "Bilibili知识区", "source": "bilibili.com", "level": "通用"},
    {"type": "平台", "name": "Coursera", "source": "coursera.org", "level": "通用"},
]


def match_school_tier(school_name: str) -> str:
    """根据学校名称匹配层级"""
    TIER_SCHOOLS = {
        "985": ["北京大学","清华大学","复旦大学","上海交通大学","浙江大学","南京大学",
                "中国科学技术大学","哈尔滨工业大学","西安交通大学","武汉大学","华中科技大学",
                "中山大学","四川大学","南开大学","天津大学","山东大学","东南大学","吉林大学",
                "同济大学","厦门大学","北京航空航天大学","北京理工大学","北京师范大学",
                "中国人民大学","大连理工大学","东北大学","华东师范大学","兰州大学",
                "西北工业大学","华南理工大学","电子科技大学","重庆大学","中南大学","湖南大学"],
        "211": ["上海财经大学","中央财经大学","对外经济贸易大学","北京邮电大学","中国政法大学",
                "北京外国语大学","上海外国语大学","西安电子科技大学","南京理工大学",
                "南京航空航天大学","华东理工大学","北京科技大学","暨南大学","西南交通大学",
                "武汉理工大学","中国海洋大学","河海大学","南京师范大学","华中师范大学",
                "郑州大学","南昌大学","苏州大学","上海大学","华南师范大学"],
        "双一流": ["中国科学院大学","南方科技大学","上海科技大学","南京医科大学","湘潭大学"],
    }
    for tier, schools in TIER_SCHOOLS.items():
        for s in schools:
            if s in school_name:
                return tier
    if any(k in school_name for k in ["职业技术学院","职业学院","专科","高职"]):
        return "专科"
    if any(k in school_name for k in ["大学","学院"]):
        return "普通本科"
    return "普通本科"


def match_subject(text: str) -> list:
    """关键词匹配学科"""
    scores = {}
    for subject, keywords in KEYWORD_MAP.items():
        score = sum(1 for kw in keywords if kw.lower() in text.lower())
        if score > 0:
            scores[subject] = score
    return sorted(scores, key=scores.get, reverse=True)


def recommend(school_name: str, query: str, count: int = 5) -> dict:
    """核心推荐函数"""
    tier = match_school_tier(school_name)
    tier_info = SCHOOL_TIERS.get(tier, SCHOOL_TIERS["普通本科"])
    subjects = match_subject(query)

    results = []
    seen = set()
    for subj in subjects:
        for r in RESOURCE_DB.get(subj, []):
            key = r["name"]
            if key not in seen:
                seen.add(key)
                results.append({**r, "subject": subj})
        if len(results) >= count:
            break

    # 兜底
    if not results:
        for r in DEFAULT_RESOURCES:
            if r["name"] not in seen:
                results.append({**r, "subject": "通用"})
            if len(results) >= count:
                break

    results = results[:count]

    # 为每个资源生成可跳转 URL
    for r in results:
        if "url" not in r or not r.get("url"):
            name = r["name"]
            source = r["source"]
            rtype = r["type"]
            encoded_name = quote(name)
            encoded_source = quote(source)
            if rtype == "课程":
                r["url"] = f"https://www.icourse163.org/search.htm?search={encoded_name}"
            elif rtype == "书籍":
                r["url"] = f"https://search.douban.com/book/subject_search?search_text={encoded_name}"
            elif rtype in ("竞赛", "平台", "工具", "框架", "项目"):
                r["url"] = f"https://www.bing.com/search?q={encoded_name}+{encoded_source}"
            elif rtype == "论文":
                r["url"] = f"https://arxiv.org/search/?query={encoded_name}"
            elif rtype in ("证书", "考试"):
                r["url"] = f"https://www.bing.com/search?q={encoded_name}+{quote('备考资料')}"
            elif rtype == "APP":
                r["url"] = f"https://www.bing.com/search?q={encoded_name}+{quote('下载')}"
            else:
                r["url"] = f"https://www.bing.com/search?q={encoded_name}"

    return {
        "school_tier": tier_info["label"],
        "tone": tier_info["tone"],
        "subjects": subjects[:3] if subjects else ["通用"],
        "resources": results,
    }
