"""配置文件"""
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a3-learning-system-secret-key-2026')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'data', 'learning.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 讯飞星火 API 配置（从环境变量或 config.json 读取）
    SPARK_APPID = os.environ.get('SPARK_APPID', '')
    SPARK_API_KEY = os.environ.get('SPARK_API_KEY', '')
    SPARK_API_SECRET = os.environ.get('SPARK_API_SECRET', '')
    SPARK_API_PASSWORD = os.environ.get('SPARK_API_PASSWORD', '')
    SPARK_API_URL = "https://spark-api-open.xf-yun.com/v1/chat/completions"
    
    # 讯飞语音识别（STT）API 配置
    STT_APPID = os.environ.get('STT_APPID', '')
    STT_API_KEY = os.environ.get('STT_API_KEY', '')
    STT_API_SECRET = os.environ.get('STT_API_SECRET', '')
    STT_API_URL = "https://spark-api.xf-yun.com/v1/chat/asr"

    # 火山引擎视频生成API配置（用于AI智能视频生成功能）
    # 文档：https://www.volcengine.com/docs/82379
    # 获取密钥：https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey
    VOLC_ACCESS_KEY = os.environ.get('VOLC_ACCESS_KEY', '')
    VOLC_SECRET_KEY = os.environ.get('VOLC_SECRET_KEY', '')
    VOLC_AK_ID = os.environ.get('VOLC_AK_ID', '')  # 火山方舟API Key（推荐方式，格式: xxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx）
    VOLC_VIDEO_MODEL = os.environ.get('VOLC_VIDEO_MODEL', 'doubao-seedance-1-0-pro-250528')  # 豆包视频生成模型
    VOLC_VIDEO_API_BASE = 'https://ark.cn-beijing.volces.com/api/v3'
    VOLC_VIDEO_SUBMIT_PATH = '/contents/generations/tasks'
    VOLC_VIDEO_QUERY_PATH = '/contents/generations/tasks/'

# 学习水平定义
LEVELS = [
    {"id": 1, "name": "基础", "icon": "🌱", "color": "#10B981", 
     "desc": "基础薄弱或刚入门，需要从核心概念开始", "score_range": (0, 40)},
    {"id": 2, "name": "中等", "icon": "🌿", "color": "#3B82F6",
     "desc": "掌握基础知识，需要系统深入理解", "score_range": (41, 70)},
    {"id": 3, "name": "高等", "icon": "🌳", "color": "#8B5CF6",
     "desc": "基础扎实，需要高阶思维和综合应用", "score_range": (71, 89)},
    {"id": 4, "name": "大神", "icon": "🏆", "color": "#F59E0B",
     "desc": "接近精通水平，需要前沿研究和创新实践", "score_range": (90, 100)},
]

DIMENSIONS = [
    {"id": "knowledge", "name": "知识掌握", "icon": "📖"},
    {"id": "understanding", "name": "理解深度", "icon": "🧠"},
    {"id": "application", "name": "应用能力", "icon": "💻"},
    {"id": "analysis", "name": "分析评价", "icon": "🔍"},
    {"id": "creativity", "name": "创新思维", "icon": "💡"},
    {"id": "self_learning", "name": "自主学习力", "icon": "📚"},
    {"id": "pace", "name": "学习节奏", "icon": "🏃"},
    {"id": "cognitive", "name": "认知层次", "icon": "🎯"},
]

RESOURCE_TYPES = {
    "course": {"name": "精品课程", "icon": "🎓"},
    "book": {"name": "推荐书籍", "icon": "📚"},
    "tool": {"name": "实用工具", "icon": "🔧"},
    "project": {"name": "项目实战", "icon": "🚀"},
    "quiz": {"name": "习题测验", "icon": "✏️"},
    "video": {"name": "视频教程", "icon": "🎬"},
    "article": {"name": "文章阅读", "icon": "📄"},
}

SUBJECTS = {
    "computer_science": "计算机科学",
    "python": "Python编程",
    "ai": "人工智能",
    "data_science": "数据科学",
    "software_engineering": "软件工程",
    "electronic": "电子信息",
    "math": "数学",
    "english": "英语",
    "finance": "金融会计",
    "law": "法学",
    "psychology": "心理学",
    "education": "教育学",
    "art_design": "艺术设计",
    "physics": "物理学",
    "chemistry": "化学",
    "biology": "生物学",
    "medicine": "医学",
    "engineering": "工程学",
    "mechanical": "机械工程",
    "civil": "土木工程",
    "electrical": "电气工程",
    "materials": "材料科学",
    "environmental": "环境科学",
    "geography": "地理学",
    "history": "历史学",
    "philosophy": "哲学",
    "politics": "政治学",
    "economics": "经济学",
    "management": "管理学",
    "marketing": "市场营销",
    "accounting": "会计学",
    "statistics": "统计学",
    "linguistics": "语言学",
    "literature": "文学",
    "music": "音乐",
    "sports": "体育",
    "agriculture": "农学",
    "architecture": "建筑学",
    "design": "设计学",
    "media": "传播学",
    "journalism": "新闻学",
    "public_health": "公共卫生",
    "nursing": "护理学",
    "pharmacy": "药学",
    "dentistry": "口腔医学",
    "veterinary": "兽医学",
    "marine": "海洋科学",
    "atmospheric": "大气科学",
    "geology": "地质学",
    "astronomy": "天文学",
    "optics": "光学",
    "robotics": "机器人学",
    "network": "网络工程",
    "database": "数据库",
    "security": "信息安全",
    "multimedia": "多媒体",
    "game": "游戏设计",
    "animation": "动画",
    "film": "影视制作",
}
