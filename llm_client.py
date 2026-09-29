"""共享LLM客户端 — 讯飞星火大模型调用
被 app.py 和 evaluation_engine.py 共用
"""
import os
import json
import requests
import time

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

SPARK_API_URL = 'https://spark-api-open.xf-yun.com/v1/chat/completions'
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

# 演示模式开关：true时跳过真实API调用，使用mock数据
DEMO_MODE = os.environ.get('DEMO_MODE', 'false').lower() == 'true'


def load_spark_config():
    """优先从环境变量加载，兼容旧版config.json"""
    config = {'api_password': os.environ.get('SPARK_API_PASSWORD', '')}
    if not config['api_password'] and os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                config['api_password'] = json.load(f).get('api_password', '')
        except:
            pass
    return config


def spark_chat(system_prompt, user_content, temperature=0.7, max_tokens=2048, max_retries=2):
    # 演示模式：跳过真实API调用
    if DEMO_MODE:
        from mock_data import get_mock_response
        result = get_mock_response(system_prompt, user_content)
        if result:
            print(f'[llm_client] DEMO_MODE 返回mock ({len(result)}字符)')
            return result

    """调用讯飞星火大模型（带重试机制）
    
    Args:
        system_prompt: 系统提示词
        user_content: 用户输入
        temperature: 温度参数
        max_tokens: 最大输出长度
        max_retries: 失败重试次数（默认2次）
    
    Returns:
        str or None: LLM返回内容，失败返回None
    """
    cfg = load_spark_config()
    api_password = cfg.get('api_password', '')
    if not api_password:
        return None

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            headers = {
                'Authorization': f'Bearer {api_password}',
                'Content-Type': 'application/json',
            }
            payload = {
                'model': 'lite',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_content}
                ],
                'temperature': temperature,
                'max_tokens': max_tokens,
            }
            resp = requests.post(SPARK_API_URL, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('choices', [{}])[0].get('message', {}).get('content', '')
            else:
                print(f'[llm_client] Spark API error: {resp.status_code} {resp.text[:200]}')
                last_error = f'HTTP {resp.status_code}'
        except requests.Timeout:
            print(f'[llm_client] Spark API timeout (attempt {attempt+1}/{max_retries+1})')
            last_error = 'timeout'
        except requests.ConnectionError as e:
            print(f'[llm_client] Spark API connection error (attempt {attempt+1}/{max_retries+1}): {e}')
            last_error = f'connection: {e}'
        except Exception as e:
            print(f'[llm_client] Spark API exception (attempt {attempt+1}/{max_retries+1}): {e}')
            last_error = str(e)
        
        if attempt < max_retries:
            # 指数退避：0.5s, 1.5s
            time.sleep(0.5 * (2 ** attempt))
    
    print(f'[llm_client] All {max_retries+1} attempts failed, last error: {last_error}')
    return None


# ===== 火山引擎视频生成API（豆包视频生成模型） =====
# 文档：https://www.volcengine.com/docs/82379/1399008
# 流程：提交任务 → 轮询任务状态 → 获取视频URL

VOLC_VIDEO_API_BASE = 'https://ark.cn-beijing.volces.com/api/v3'


def _load_volc_config():
    """加载火山引擎视频API配置（优先 ARK_API_KEY）"""
    # 优先使用用户提供的 ARK_API_KEY（火山方舟 API Key）
    api_key = os.environ.get('ARK_API_KEY', '')
    if not api_key:
        api_key = os.environ.get('VOLC_AK_ID', '')
    if not api_key:
        # 兼容config.json
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    api_key = json.load(f).get('volc_ak_id', '')
            except Exception:
                pass
    return {
        'api_key': api_key,
        'model': os.environ.get('VOLC_VIDEO_MODEL', 'doubao-seedance-1-0-pro-250528'),
    }


def volc_video_enabled():
    """检查火山引擎视频生成API是否已配置"""
    return bool(_load_volc_config()['api_key'])


def volc_video_submit(prompt, model=None, duration=5, resolution='720p', aspect_ratio='16:9'):
    """提交视频生成任务（异步）

    Args:
        prompt: 视频生成提示词（中英文皆可）
        model: 模型名（默认读取配置）
        duration: 视频时长（秒），5或10
        resolution: 分辨率 720p/1080p
        aspect_ratio: 宽高比 16:9 / 9:16 / 1:1

    Returns:
        dict: {"task_id": "...", "success": True} 或 {"success": False, "error": "..."}
    """
    cfg = _load_volc_config()
    if not cfg['api_key']:
        return {
            "success": False,
            "error": "未配置火山引擎API密钥。请在 .env 中设置 VOLC_AK_ID（火山方舟API Key）。"
                     "获取地址：https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey"
        }

    model_name = model or cfg['model']
    try:
        headers = {
            'Authorization': f'Bearer {cfg["api_key"]}',
            'Content-Type': 'application/json',
        }
        payload = {
            "model": model_name,
            "content": [
                {"type": "text", "text": prompt}
            ],
            # 视频参数（火山引擎支持的可选参数）
            "duration": duration,
            "resolution": resolution,
            "ratio": aspect_ratio,
        }
        resp = requests.post(
            f"{VOLC_VIDEO_API_BASE}/contents/generations/tasks",
            headers=headers, json=payload, timeout=20
        )
        if resp.status_code == 200:
            data = resp.json()
            task_id = data.get('id') or data.get('task_id')
            if task_id:
                return {"success": True, "task_id": task_id, "model": model_name}
            return {"success": False, "error": f"API响应异常: {data}"}
        else:
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
    except requests.Timeout:
        return {"success": False, "error": "提交视频生成任务超时（15秒）"}
    except Exception as e:
        return {"success": False, "error": f"提交异常: {e}"}


def volc_video_query(task_id):
    """查询视频生成任务状态

    Returns:
        dict: {
            "success": True,
            "status": "queued" | "running" | "succeeded" | "failed",
            "video_url": "..." (status=succeeded时),
            "progress": 0-100,
            "error": "..." (status=failed时)
        }
    """
    cfg = _load_volc_config()
    if not cfg['api_key']:
        return {"success": False, "error": "未配置火山引擎API密钥"}

    try:
        headers = {'Authorization': f'Bearer {cfg["api_key"]}'}
        resp = requests.get(
            f"{VOLC_VIDEO_API_BASE}/contents/generations/tasks/{task_id}",
            headers=headers, timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            status = data.get('status', 'unknown')
            result = {"success": True, "status": status, "raw": data}
            
            # 计算进度（根据状态估算）
            progress_map = {
                'queued': 10,
                'pending': 10,
                'running': 50,
                'processing': 50,
                'succeeded': 100,
                'completed': 100,
                'failed': 0,
            }
            result['progress'] = progress_map.get(status, 30)
            
            # 提取视频URL（成功状态）
            content = data.get('content') or {}
            if isinstance(content, dict):
                # 新版返回结构：content.video_url
                if content.get('video_url'):
                    result['video_url'] = content['video_url']
                # 旧版返回结构：content.videos[0].url
                videos = content.get('videos') or []
                if videos and len(videos) > 0:
                    result['video_url'] = videos[0].get('url')
                    result['cover_url'] = videos[0].get('cover_image_url')
            # 兼容另一种返回结构
            if not result.get('video_url') and data.get('video_url'):
                result['video_url'] = data.get('video_url')
            # 错误信息
            if status == 'failed':
                result['error'] = data.get('error', {}).get('message', '视频生成失败')
            return result
        else:
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": f"查询异常: {e}"}


# ===== Python代码AI批改（基于讯飞星火大模型） =====
def evaluate_python_code(student_code, task_description="", reference_answer="", agent_name='CodeEvaluator'):
    """使用LLM评估学生Python代码

    Args:
        student_code: 学生提交的Python代码
        task_description: 题目要求描述
        reference_answer: 参考答案（可选）

    Returns:
        dict: {
            "success": True,
            "score": 0-100,
            "overall_comment": "整体评价",
            "issues": [{"line": int, "severity": "high|medium|low", "issue": "...", "suggestion": "..."}, ...],
            "correctness": "correct|partial|incorrect",
            "raw_response": "..."
        }
    """
    if not student_code or not student_code.strip():
        return {"success": False, "error": "代码为空"}

    sys_prompt = (
        "你是一名严谨的Python编程教师，负责批改学生代码。"
        "请基于题目要求逐行分析学生代码，找出逻辑错误、语法错误、规范问题，并给出具体修改建议。"
        "只输出JSON，不要其他文字。"
    )
    user_prompt = (
        f"## 题目要求\n{task_description or '完成指定功能的Python程序'}\n\n"
        f"## 参考答案（仅供参考）\n```\n{reference_answer or '（无参考答案）'}\n```\n\n"
        f"## 学生代码\n```\n{student_code}\n```\n\n"
        "## 评估要求\n"
        "1. 判断代码整体正确性（correct完全正确 / partial部分正确 / incorrect错误）\n"
        "2. 给出0-100的整数分数\n"
        "3. 逐行找出问题，每条问题包含：行号(line)、严重程度(severity: high/medium/low)、问题描述(issue)、修改建议(suggestion)\n"
        "4. 给出整体评语\n\n"
        "## 输出JSON格式\n"
        '{"correctness": "correct|partial|incorrect", "score": 85, '
        '"overall_comment": "整体评价", '
        '"issues": [{"line": 5, "severity": "high", "issue": "问题描述", "suggestion": "修改建议"}]}'
    )
    try:
        llm_result = spark_chat(sys_prompt, user_prompt, temperature=0.2, max_tokens=2048)
        if not llm_result:
            return {"success": False, "error": "AI评估服务暂不可用，请稍后重试"}

        # 解析JSON
        import re
        m = re.search(r'\{.*\}', llm_result, re.DOTALL)
        if not m:
            return {"success": False, "error": "AI响应格式异常", "raw_response": llm_result}
        parsed = json.loads(m.group())
        parsed['success'] = True
        parsed['raw_response'] = llm_result
        return parsed
    except Exception as e:
        return {"success": False, "error": f"评估异常: {e}", "raw_response": llm_result if 'llm_result' in dir() else ''}
