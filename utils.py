"""
共享工具函数模块 — 消除 app.py 中的重复代码
"""
import json, hmac, base64, hashlib, urllib.parse, logging, re as _re
from datetime import datetime, timedelta
from models import db, User, Assessment, EvaluationReport, ProfileConversation, KnowledgePoint, LearningBehavior, WrongQuestion

logger = logging.getLogger(__name__)

def call_llm(system_prompt, user_content):
    """统一LLM调用：先走讯飞（含演示模式兜底）"""
    from llm_client import spark_chat, DEMO_MODE
    if DEMO_MODE:
        from mock_data import get_mock_response
        result = get_mock_response(system_prompt, user_content)
        if result:
            logger.info(f'[utils] DEMO_MODE 返回mock ({len(result)}字符)')
            return result
    return spark_chat(system_prompt, user_content)


def call_llm_json(system_prompt, user_content, allow_list=False, agent_name='Agent'):
    """调用LLM并从响应中提取JSON对象
    
    Args:
        system_prompt: 系统提示词
        user_content: 用户输入
        allow_list: 是否允许顶层数组（True时搜索[...]）
        agent_name: 用于日志的Agent名称
    Returns:
        dict|list|None: 提取的JSON对象，失败返回None
    """
    llm_result = call_llm(system_prompt, user_content)
    if not llm_result:
        logger.warning(f"[{agent_name}] LLM返回为空")
        return None
    
    try:
        # 优先搜dict，次选搜array
        pattern = r'\{.*\}' if not allow_list else r'(\{.*\}|\[.*\])'
        _m = _re.search(pattern, llm_result, _re.DOTALL)
        if not _m:
            logger.warning(f"[{agent_name}] LLM响应中未找到JSON: {llm_result[:100]}...")
            return None
        parsed = json.loads(_m.group())
        return parsed
    except Exception as e:
        logger.warning(f"[{agent_name}] JSON解析失败: {e}")
        return None


# ===== 讯飞语音识别（STT）签名与调用 =====
# 设计原则：语音输入只作为「快捷方式」而不是「必要入口」
# 当语音服务不可用时，自动降级为模拟模式，核心流程不受影响

def generate_stt_signature(api_key, api_secret, url):
    """生成讯飞STT API签名"""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # 构建签名原始字符串
    signature_origin = f"host: {host}\ndate: {date}\nGET /{parsed.path.split('/')[-1]} HTTP/1.1"
    
    # HMAC-SHA256 加密
    sign = hmac.new(api_secret.encode('utf-8'), signature_origin.encode('utf-8'), hashlib.sha256).digest()
    sign_base64 = base64.b64encode(sign).decode('utf-8')
    
    # 构建 Authorization
    authorization = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{sign_base64}"'
    )
    
    return date, authorization


def get_stt_mock_text():
    """生成模拟语音识别结果，确保核心流程可继续运行"""
    mock_results = [
        "请帮我分析一下这个知识点",
        "我想了解更多关于机器学习的内容",
        "这道题怎么做",
        "讲解一下递归函数",
        "帮我生成一份学习计划",
        "这个概念不太理解",
        "请详细解释一下",
        "给我一些练习题",
        "我需要复习一下前面的内容",
        "这个算法的时间复杂度是多少",
        "什么是深度学习",
        "如何优化代码性能",
        "解释一下面向对象编程",
        "数据库索引有什么作用",
        "什么是时间复杂度"
    ]
    import random
    return random.choice(mock_results)


def stt_recognize(audio_bytes):
    """调用讯飞语音识别API（软隔离模式）
    
    软隔离设计：当STT服务不可用（未配置密钥、网络故障、超时）时，
    返回模拟文本，确保调用方核心流程不受影响。
    
    Returns:
        dict: {'text': str, 'mode': str, 'hint': str}
            mode: 'real' | 'mock' | 'timeout_fallback' | 'error_fallback' | 'empty_fallback'
    """
    from config import Config as AppConfig
    import threading
    
    # 从环境变量获取讯飞语音识别配置
    appid = os.environ.get('IFLYTEK_APPID', AppConfig.IFLYTEK_APPID)
    api_key = os.environ.get('IFLYTEK_API_KEY', AppConfig.IFLYTEK_API_KEY)
    api_secret = os.environ.get('IFLYTEK_API_SECRET', AppConfig.IFLYTEK_API_SECRET)
    
    # 软隔离：配置不全时返回模拟结果，不阻断流程
    if not all([appid, api_key, api_secret]):
        logger.warning("讯飞STT配置不全，使用模拟识别")
        return {
            "text": get_stt_mock_text(),
            "mode": "mock",
            "hint": "语音服务暂未配置，当前为模拟模式"
        }
    
    url = f"wss://iat-api.xfyun.cn/v2/iat"
    
    try:
        date, authorization = generate_stt_signature(api_key, api_secret, url)
    except Exception as e:
        logger.error(f"STT签名生成失败: {e}")
        return {
            "text": get_stt_mock_text(),
            "mode": "error_fallback",
            "hint": "语音识别签名生成失败，已切换至模拟模式"
        }
    
    # 构建鉴权URL
    host = urllib.parse.urlparse(url).hostname
    auth_url = (
        f"wss://{host}/v2/iat?"
        f"authorization={urllib.parse.quote(authorization)}&"
        f"date={urllib.parse.quote(date)}&"
        f"host={host}"
    )
    
    try:
        import websocket
        
        result_text = []
        ws_error = None
        ws_closed = False
        timeout_event = threading.Event()
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get('code') == 0:
                    for result in data.get('data', {}).get('result', {}).get('ws', []):
                        for w in result.get('cw', []):
                            result_text.append(w.get('w', ''))
                else:
                    logger.warning(f"STT识别错误: {data.get('message', '')}")
            except Exception as e:
                logger.error(f"STT消息解析失败: {e}")
        
        def on_error(ws, error):
            nonlocal ws_error
            ws_error = str(error)
            logger.error(f"STT WebSocket错误: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            nonlocal ws_closed
            ws_closed = True
        
        def on_open(ws):
            def run(*args):
                frame_size = 1280
                for i in range(0, len(audio_bytes), frame_size):
                    if timeout_event.is_set():
                        ws.close()
                        return
                    chunk = audio_bytes[i:i+frame_size]
                    ws.send(chunk, websocket.ABNF.OPCODE_BINARY)
                ws.send('{}', websocket.ABNF.OPCODE_TEXT)
            
            import _thread as thread
            thread.start_new_thread(run, ())
        
        ws = websocket.WebSocketApp(
            auth_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # 超时保护：15秒超时后自动降级
        def timeout_handler():
            import time
            time.sleep(15)
            if not ws_closed:
                timeout_event.set()
                ws.close()
        
        timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        timeout_thread.start()
        
        try:
            ws.run_forever(ping_interval=5, ping_timeout=8)
        except Exception as ws_e:
            logger.error(f"STT连接异常: {ws_e}")
        
        # 超时处理：返回模拟结果
        if timeout_event.is_set():
            logger.warning("STT调用超时，自动降级为模拟模式")
            return {
                "text": get_stt_mock_text(),
                "mode": "timeout_fallback",
                "hint": "语音识别超时，已切换至模拟模式"
            }
        
        # API错误处理：返回模拟结果
        if ws_error:
            logger.error(f"STT错误: {ws_error}")
            return {
                "text": get_stt_mock_text(),
                "mode": "error_fallback",
                "hint": "语音识别服务异常，已切换至模拟模式"
            }
        
        recognized = ''.join(result_text)
        
        # 识别结果为空时也返回模拟结果
        if not recognized:
            logger.warning("STT识别结果为空，使用模拟模式")
            return {
                "text": get_stt_mock_text(),
                "mode": "empty_fallback",
                "hint": "语音无法识别，已切换至模拟模式"
            }
        
        return {"text": recognized, "mode": "real", "hint": "语音识别成功"}
        
    except ImportError as e:
        logger.error(f"STT依赖缺失: {e}")
        return {
            "text": get_stt_mock_text(),
            "mode": "dependency_fallback",
            "hint": "语音识别依赖缺失，已切换至模拟模式"
        }
    except Exception as e:
        logger.error(f"STT调用异常: {e}")
        return {
            "text": get_stt_mock_text(),
            "mode": "general_fallback",
            "hint": "语音识别异常，已切换至模拟模式"
        }


# ===== 认知弱点提取（消除913-1023和1375-1426的重复代码） =====
def get_weakness_points(student_id, focus_weakness=None, max_points=10):
    """从评估报告/测评/画像中提取学生的认知弱点
    
    Args:
        student_id: 学生ID
        focus_weakness: 可选，指定的弱点名称
        max_points: 最大返回数量
    Returns:
        list: 弱点列表
    """
    weak_points = []
    
    # 1. 从 EvaluationReport 获取弱点数据（优先）
    reports = EvaluationReport.query.filter_by(user_id=student_id).order_by(
        EvaluationReport.created_at.desc()
    ).limit(3).all()
    
    for report in reports:
        if report.weaknesses:
            try:
                weaknesses = json.loads(report.weaknesses)
                if isinstance(weaknesses, list):
                    weak_points.extend(weaknesses)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    
    # 2. 从 Assessment 获取薄弱维度
    assessments = Assessment.query.filter_by(user_id=student_id).order_by(
        Assessment.created_at.desc()
    ).limit(3).all()
    
    for assessment in assessments:
        if assessment.dimension_scores:
            try:
                dim_scores = json.loads(assessment.dimension_scores)
                for dim, score in dim_scores.items():
                    if isinstance(score, (int, float)) and score < 60:
                        weak_points.append(f"{dim}掌握不足")
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    
    # 3. 从 ProfileConversation 获取困难描述
    profile_chats = ProfileConversation.query.filter_by(
        user_id=student_id, is_complete=True
    ).order_by(ProfileConversation.updated_at.desc()).limit(1).all()
    
    for pc in profile_chats:
        if pc.profile_data:
            try:
                profile = json.loads(pc.profile_data)
                difficulties = profile.get('difficulties', '')
                if isinstance(difficulties, list):
                    weak_points.extend(difficulties)
                elif isinstance(difficulties, str):
                    for item in difficulties.split('，'):
                        item = item.strip()
                        if item and len(item) > 2:
                            weak_points.append(item)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    
    # 去重
    weak_points = list(set(weak_points))[:max_points]
    
    # 如果指定了弱点名称，优先使用该弱点
    if focus_weakness:
        if focus_weakness in weak_points:
            weak_points.remove(focus_weakness)
        weak_points.insert(0, focus_weakness)
    
    return weak_points


# ===== 记忆温度计（知识热度） =====

# 画像认知风格 → 衰减系数映射
# 不同认知风格的学习者遗忘速度不同
COGNITIVE_STYLE_DECAY_FACTOR = {
    '视觉型': 1.15,     # 视觉型学习者记忆更持久，衰减更慢
    '听觉型': 1.0,      # 标准衰减
    '动手型': 1.05,     # 动手实践有助于记忆
    '综合型': 1.0,      # 标准衰减
    '分析型': 1.1,      # 分析型深度理解，衰减较慢
    '记忆型': 0.85,     # 记忆型靠机械记忆，衰减更快
}

# 画像学习节奏 → 复习间隔调整
LEARNING_PACE_FACTOR = {
    'fast': 0.9,    # 快节奏学习者需要更频繁复习
    'medium': 1.0,  # 标准节奏
    'slow': 1.2,    # 慢节奏学习者间隔更长
}


def calculate_memory_temperature(last_study_time, mastery_level, user_id=None):
    """根据遗忘曲线计算知识点的记忆温度（0-100度）
    
    与用户画像联动：
    - 认知风格影响衰减速度（视觉型衰减慢，记忆型衰减快）
    - 学习节奏影响复习间隔
    - 画像薄弱维度的知识点衰减更快（需重点关注）
    """
    if last_study_time is None:
        return 0.0
    
    now = datetime.utcnow()
    if isinstance(last_study_time, str):
        last_study_time = datetime.fromisoformat(last_study_time.replace('Z', '+00:00'))
    
    # 计算距离上次复习的小时数
    hours_passed = (now - last_study_time).total_seconds() / 3600
    
    # 初始温度为100度（刚学习完）
    initial_temp = 100
    
    # 衰减速度受掌握程度影响：掌握程度越高衰减越慢
    base_decay_hours = 24
    decay_hours = base_decay_hours * (1 + mastery_level * 4)
    
    # 与用户画像联动：获取认知风格和学习节奏调整衰减
    profile_multiplier = 1.0
    if user_id:
        try:
            profile_ctx = get_student_profile_context(user_id)
            if profile_ctx.get('has_profile'):
                cognitive_style = profile_ctx.get('cognitive_style', '综合型')
                # 认知风格影响衰减系数
                style_factor = COGNITIVE_STYLE_DECAY_FACTOR.get(cognitive_style, 1.0)
                profile_multiplier *= style_factor
        except Exception:
            pass  # 画像获取失败时使用默认衰减
    
    # 指数衰减公式（乘以画像系数）
    temperature = initial_temp * (0.95 ** (hours_passed / (decay_hours / 24))) * profile_multiplier
    
    return max(0, min(100, temperature))


def get_temperature_status(temperature):
    """根据温度值返回状态描述"""
    if temperature >= 80:
        return "稳固", "hot"
    elif temperature >= 50:
        return "需关注", "warm"
    elif temperature >= 30:
        return "危险", "cold"
    else:
        return "濒危遗忘", "critical"


def check_memory_temperature(student_id):
    """检查所有知识点的记忆温度（与用户画像联动）"""
    from config import SUBJECTS
    points = KnowledgePoint.query.filter_by(user_id=student_id).all()
    results = []
    
    for point in points:
        temperature = calculate_memory_temperature(point.last_study_time, point.mastery_level, user_id=student_id)
        status, level = get_temperature_status(temperature)
        subject_name = SUBJECTS.get(point.subject, point.subject) if point.subject else '未知学科'
        results.append({
            'id': point.id,
            'name': point.name,
            'subject': point.subject,
            'subject_name': subject_name,
            'temperature': round(temperature, 2),
            'status': status,
            'level': level,
            'mastery_level': point.mastery_level,
            'study_count': point.study_count if hasattr(point, 'study_count') and point.study_count else 0,
            'last_study_time': point.last_study_time.isoformat() if point.last_study_time else None,
            'last_study': point.last_study_time.strftime('%Y-%m-%d %H:%M') if point.last_study_time else '从未学习',
            'remind_date': point.remind_date.isoformat() if hasattr(point, 'remind_date') and point.remind_date else None
        })
    
    # 按温度升序排列（最需要复习的在前）
    results.sort(key=lambda x: x['temperature'])
    return results


def extract_knowledge_points(text, subject):
    """从文本中提取知识点"""
    import re
    points = []
    
    patterns = [
        r'(?:关于|学习|掌握|理解|熟悉|重点|核心)\s*[：:]\s*([^，。；\n]{2,30})',
        r'(?:知识点|概念|原理|定义|定理|公式|算法|模型)\s*[：:]\s*([^，。；\n]{2,30})',
        r'(?:讲解|介绍|分析|探讨)\s*[：:]\s*([^，。；\n]{2,30})',
        r'(?:学习内容|学习目标|掌握内容)\s*[：:]\s*([^，。；\n]{2,30})',
        r'(?:第[一二三四五六七八九十\d]+[章节课讲])\s*[：:]\s*([^，。；\n]{2,30})',
        r'(?:掌握程度|知识掌握|认知水平)\s*[：:]\s*([^，。；\n]{2,30})',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        points.extend([(m.strip(), subject) for m in matches if len(m.strip()) >= 2])
    
    if not points:
        keywords = re.findall(r'([\u4e00-\u9fa5]{2,8})\s*(?:是|指|包括|涉及)', text)
        points.extend([(k.strip(), subject) for k in keywords if len(k.strip()) >= 2])
    
    if not points:
        segments = re.split(r'[，。；！？\n]', text)
        for seg in segments:
            seg = seg.strip()
            if len(seg) >= 4 and len(seg) <= 20:
                if any(char in seg for char in ['学', '知', '识', '概', '念', '原', '理', '算', '法', '模', '型']):
                    points.append((seg, subject))
    
    return list(set(points))[:10]


def add_or_update_knowledge_point(user_id, subject, name, mastery_score=None):
    """添加或更新知识点"""
    existing = KnowledgePoint.query.filter_by(
        user_id=user_id, subject=subject, name=name
    ).first()
    
    if existing:
        existing.last_study_time = datetime.utcnow()
        if mastery_score is not None:
            existing.mastery_level = (existing.mastery_level * existing.study_count + mastery_score / 100.0) / (existing.study_count + 1)
        existing.study_count += 1
        db.session.commit()
        return existing
    
    point = KnowledgePoint(
        user_id=user_id,
        subject=subject,
        name=name,
        mastery_level=(mastery_score or 50) / 100.0,
        last_study_time=datetime.utcnow(),
    )
    db.session.add(point)
    db.session.commit()
    return point


def update_knowledge_point_remind_date(point_id, date):
    """更新知识点的提醒日期"""
    point = KnowledgePoint.query.get(point_id)
    if point:
        point.remind_date = date
        db.session.commit()
        return True
    return False


def get_student_profile_context(user_id):
    """
    获取学生的个性化画像数据，供多智能体协作使用
    
    返回字典包含:
    - has_profile: bool
    - dimension_scores: dict (8维画像分数)
    - cognitive_style: str (认知风格)
    - weak_points: list (薄弱维度列表)
    - strong_points: list (优势维度列表)
    - level: int (综合等级)
    - level_name: str (等级名称)
    - goal: str (学习目标)
    - major: str (专业)
    """
    from models import ProfileConversation, Assessment, EvaluationReport
    
    result = {
        'has_profile': False,
        'dimension_scores': {},
        'cognitive_style': '综合型',
        'weak_points': [],
        'strong_points': [],
        'level': 1,
        'level_name': '基础',
        'goal': '',
        'major': '',
    }
    
    # 1. 加载最新画像
    latest_profile = ProfileConversation.query.filter_by(
        user_id=user_id, is_complete=True
    ).order_by(ProfileConversation.updated_at.desc()).first()
    
    if latest_profile and latest_profile.profile_data:
        try:
            profile = json.loads(latest_profile.profile_data)
            if isinstance(profile, dict):
                result['has_profile'] = True
                result['dimension_scores'] = profile.get('dimension_scores', {})
                result['cognitive_style'] = profile.get('cognitive_style', '综合型')
                result['weak_points'] = profile.get('weak_points', [])
                result['strong_points'] = profile.get('strong_points', [])
                result['level'] = profile.get('level', 1)
                result['level_name'] = profile.get('level_name', '基础')
                result['goal'] = profile.get('goal', '')
                result['major'] = profile.get('major', '')
        except (json.JSONDecodeError, TypeError):
            pass
    
    # 2. 补充最新评估中的薄弱项（优先级高于画像中的weak_points）
    latest_eval = EvaluationReport.query.filter_by(
        user_id=user_id
    ).order_by(EvaluationReport.created_at.desc()).first()
    if latest_eval and latest_eval.weaknesses:
        try:
            eval_weaknesses = json.loads(latest_eval.weaknesses) if isinstance(latest_eval.weaknesses, str) else latest_eval.weaknesses
            if isinstance(eval_weaknesses, list) and eval_weaknesses:
                # 合并画像weak_points和评估weaknesses，去重
                existing = set(result['weak_points'])
                for w in eval_weaknesses:
                    if isinstance(w, str) and w not in existing:
                        result['weak_points'].append(w)
                        existing.add(w)
        except (json.JSONDecodeError, TypeError):
            pass
    
    return result


# ===== 错题记录与管理 =====

def record_wrong_question(user_id, subject, question, correct_answer=None, user_answer=None,
                           question_type='choice', knowledge_point=None, difficulty='medium',
                           source='assessment'):
    """记录一道错题到数据库
    
    Args:
        user_id: 学生ID
        subject: 学科
        question: 题目内容
        correct_answer: 正确答案
        user_answer: 学生答案
        question_type: 题型 (choice/fill/essay/trap)
        knowledge_point: 关联知识点名称
        difficulty: 难度 (easy/medium/hard)
        source: 来源 (assessment/trap_exam/quiz)
    Returns:
        WrongQuestion 对象
    """
    wq = WrongQuestion(
        user_id=user_id,
        subject=subject,
        question=question,
        correct_answer=correct_answer,
        user_answer=user_answer,
        question_type=question_type,
        knowledge_point=knowledge_point,
        difficulty=difficulty,
        source=source,
    )
    db.session.add(wq)
    db.session.commit()
    
    # 同时更新/创建关联知识点的记忆温度（错题说明掌握度低）
    if knowledge_point:
        add_or_update_knowledge_point(user_id, subject, knowledge_point, mastery_score=30)
    
    return wq


def get_wrong_questions(user_id, subject=None, only_unmastered=False, limit=50):
    """获取学生的错题列表
    
    Args:
        user_id: 学生ID
        subject: 学科过滤（可选）
        only_unmastered: 是否只返回未掌握的错题
        limit: 最大返回数量
    Returns:
        list: 错题列表
    """
    query = WrongQuestion.query.filter_by(user_id=user_id)
    if subject:
        query = query.filter_by(subject=subject)
    if only_unmastered:
        query = query.filter_by(is_mastered=False)
    query = query.order_by(WrongQuestion.created_at.desc())
    return query.limit(limit).all()


def mark_wrong_question_mastered(wq_id, user_id):
    """标记错题为已掌握
    
    Args:
        wq_id: 错题ID
        user_id: 学生ID（验证权限）
    Returns:
        bool: 是否成功
    """
    wq = WrongQuestion.query.filter_by(id=wq_id, user_id=user_id).first()
    if not wq:
        return False
    
    wq.is_mastered = True
    wq.mastered_at = datetime.utcnow()
    wq.review_count += 1
    wq.last_review_time = datetime.utcnow()
    db.session.commit()
    
    # 同时提升关联知识点的掌握度
    if wq.knowledge_point:
        add_or_update_knowledge_point(user_id, wq.subject, wq.knowledge_point, mastery_score=75)
    
    return True


def get_wrong_question_stats(user_id, subject=None):
    """获取错题统计
    
    Returns:
        dict: {total, unmastered, mastered, by_subject, by_difficulty}
    """
    query = WrongQuestion.query.filter_by(user_id=user_id)
    if subject:
        query = query.filter_by(subject=subject)
    
    all_wq = query.all()
    total = len(all_wq)
    unmastered = sum(1 for w in all_wq if not w.is_mastered)
    mastered = total - unmastered
    
    by_subject = {}
    by_difficulty = {'easy': 0, 'medium': 0, 'hard': 0}
    for w in all_wq:
        by_subject[w.subject] = by_subject.get(w.subject, 0) + 1
        if w.difficulty in by_difficulty:
            by_difficulty[w.difficulty] += 1
    
    return {
        'total': total,
        'unmastered': unmastered,
        'mastered': mastered,
        'by_subject': by_subject,
        'by_difficulty': by_difficulty,
    }


# ===== 定时复习提醒检查 =====

def get_review_reminders(user_id):
    """获取需要复习的提醒（濒危知识点 + 未掌握错题）
    
    每天只提醒一次（基于 last_remind_date 去重）
    
    Returns:
        dict: {critical_points, wrong_questions, summary}
    """
    from datetime import date
    today = date.today()
    
    # 1. 检查濒危知识点（温度 < 30）
    points = KnowledgePoint.query.filter(
        KnowledgePoint.user_id == user_id,
        (KnowledgePoint.last_remind_date != today) | (KnowledgePoint.last_remind_date.is_(None))
    ).all()
    
    critical_points = []
    for point in points:
        temperature = calculate_memory_temperature(point.last_study_time, point.mastery_level, user_id=user_id)
        if temperature < 30:
            point.last_remind_date = today
            db.session.add(point)
            critical_points.append({
                'id': point.id,
                'name': point.name,
                'subject': point.subject,
                'temperature': round(temperature, 1),
            })
    
    # 2. 检查未掌握错题（创建超过1天且未复习的）
    from sqlalchemy import or_
    overdue_wrong = WrongQuestion.query.filter(
        WrongQuestion.user_id == user_id,
        WrongQuestion.is_mastered == False,
        WrongQuestion.created_at < datetime.utcnow() - timedelta(hours=24),
        or_(
            WrongQuestion.last_review_time.is_(None),
            WrongQuestion.last_review_time < datetime.utcnow() - timedelta(hours=48)
        )
    ).limit(10).all()
    
    wrong_reminders = []
    for wq in overdue_wrong:
        wrong_reminders.append({
            'id': wq.id,
            'question': wq.question[:80] + '...' if len(wq.question) > 80 else wq.question,
            'subject': wq.subject,
            'knowledge_point': wq.knowledge_point,
            'difficulty': wq.difficulty,
        })
    
    db.session.commit()
    
    return {
        'critical_points': critical_points,
        'wrong_questions': wrong_reminders,
        'summary': {
            'critical_count': len(critical_points),
            'wrong_count': len(wrong_reminders),
            'total': len(critical_points) + len(wrong_reminders),
        }
    }
