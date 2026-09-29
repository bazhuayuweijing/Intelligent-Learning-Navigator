"""
评估引擎 - 大模型驱动的学习效果评估
功能：
1. 多维度行为数据分析
2. LLM驱动的综合评估
3. 动态学习计划调整
4. 防幻觉与内容安全过滤
"""
import json
import random
import re
from datetime import datetime, timedelta
from models import db, LearningBehavior, EvaluationReport, LearningPlan, ContentSafetyLog, AsyncTask, Assessment, ResourceHistory

# ================================================================
# 维度定义
# ================================================================
EVAL_DIMENSIONS = [
    {"id": "knowledge", "name": "知识掌握", "weight": 0.22, "desc": "核心概念、理论与基本原理的理解程度"},
    {"id": "understanding", "name": "理解深度", "weight": 0.18, "desc": "能否解释原理、机制与内在逻辑"},
    {"id": "application", "name": "应用能力", "weight": 0.22, "desc": "能否独立解决实际问题、完成编程任务"},
    {"id": "analysis", "name": "分析评价", "weight": 0.15, "desc": "能否评估不同方案优劣、分析错误原因"},
    {"id": "creativity", "name": "创新思维", "weight": 0.15, "desc": "能否创新性组合知识、提出新方案"},
    {"id": "self_learning", "name": "自主学习力", "weight": 0.08, "desc": "主动学习、规划与坚持的能力"},
]

# ================================================================
# 安全过滤 - 防幻觉与内容审核
# ================================================================
class SafetyFilter:
    """内容安全过滤与防幻觉审核"""
    
    # 学术事实性关键词检查白名单
    FACTUAL_CHECKLIST = {
        'ai': {
            'patterns': [
                (r'CNN|卷积神经网络', 'CNN is a feedforward network with convolutional layers'),
                (r'RNN|循环神经网络', 'RNN has recurrent connections for sequence data'),
                (r'Transformer', 'Transformer uses self-attention mechanism'),
                (r'梯度下降|gradient descent', 'Gradient descent optimizes loss via gradients'),
                (r'过拟合|overfitting', 'Overfitting: model performs well on training but poorly on test'),
                (r'SGD|随机梯度下降', 'SGD updates parameters using a single sample per iteration'),
                (r'ReLU', 'ReLU activation: f(x)=max(0,x)'),
                (r'Batch Normalization|批归一化', 'BN normalizes layer inputs to stabilize training'),
                (r'Dropout', 'Dropout randomly drops neurons to prevent co-adaptation'),
            ]
        },
        'python': {
            'patterns': [
                (r'列表推导|list comprehension', 'List comprehension: [expr for item in iterable if condition]'),
                (r'装饰器|decorator', 'Decorator is a function that takes another function as argument'),
                (r'GIL', 'GIL limits CPython to one thread executing at a time'),
                (r'asyncio', 'asyncio is for concurrent code using async/await syntax'),
            ]
        }
    }
    
    # 敏感内容关键词列表（硬违规 - 必须拦截）
    SENSITIVE_PATTERNS = [
        (r'(色情|赌博|暴力|毒品|枪支|恐怖|政治敏感|翻墙|VPN[^a-z])', '违法违规内容'),
        (r'(代考|代写|作弊|替考|买分|卖分)', '学术不端行为'),
        (r'(黑客攻击|DDOS|入侵|窃取)', '网络攻击行为'),
        (r'(自杀|自残|跳楼|割腕|想死|活不下去)', '危险行为'),
        (r'(造假|伪造|篡改|捏造数据|数据造假)', '学术造假'),
        (r'(歧视|种族歧视|性别歧视|地域歧视)', '歧视言论'),
        (r'(傻逼|蠢货|废物|垃圾|去死|滚)', '辱骂攻击'),
        (r'(东北佬|河南骗子|黑人|白皮猪|小日本)', '地域/族群攻击'),
    ]
    
    # 绝对化/过度承诺表述（软违规 - 需要弱化处理）
    OVERPROMISE_PATTERNS = [
        r'(保证学会|保证掌握|保证通过)',
        r'(确保学会|确保掌握|确保通过)',
        r'(绝对[^不]|100%[^以])',
        r'(肯定[^不]|必定|一定能)',
    ]
    
    @classmethod
    def check_factual_accuracy(cls, text, subject='ai'):
        """检查学术内容的事实准确性"""
        issues = []
        if subject not in cls.FACTUAL_CHECKLIST:
            return issues
        
        for pattern, expected_desc in cls.FACTUAL_CHECKLIST[subject]['patterns']:
            if re.search(pattern, text, re.IGNORECASE):
                lines = text.split('\n')
                relevant_lines = [l for l in lines if re.search(pattern, l, re.IGNORECASE)]
                for line in relevant_lines:
                    if '反向传播' in line and '不需要' in line and '梯度' in line:
                        issues.append(f"事实错误：反向传播需要计算梯度")
                    if 'CNN' in line and '全连接' in line and not '卷积' in line:
                        issues.append(f"事实不准确：CNN核心是卷积层而非全连接层")
                    if 'Transformer' in line and '不使用' in line and '注意力' in line:
                        issues.append(f"事实错误：Transformer基于自注意力机制")
                    if 'ReLU' in line and '负数' in line and '激活' in line and '可以' in line:
                        issues.append(f"事实错误：ReLU对负数输入输出为0")
        
        return issues
    
    @classmethod
    def check_sensitive_content(cls, text):
        """检查敏感/违规内容（硬违规）"""
        flags = []
        for pattern, category in cls.SENSITIVE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                flags.append(f"内容安全告警[{category}]：包含敏感词 '{matches[0]}'")
        return flags
    
    @classmethod
    def check_overpromise(cls, text):
        """检测过度承诺（软违规）"""
        issues = []
        overpromise_count = 0
        
        for pattern in cls.OVERPROMISE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                overpromise_count += 1
        
        if overpromise_count >= 2:
            issues.append(f"过度承诺风险：检测到{overpromise_count}处绝对化表述，可能存在夸大宣传")
        
        return issues
    
    @classmethod
    def check_hallucination_risk(cls, text, context=None):
        """检测幻觉风险"""
        risks = []
        
        # 1. 虚假引用检测 - 检测含糊的学术引用
        fake_ref_patterns = [
            r'(?:参见|引用|参考|基于)[^。，；]*?某论文[^。，；]*?(?:20\d{2})',
            r'(?:参见|引用|参考|基于)[^。，；]*?一篇论文[^。，；]*?(?:20\d{2})',
            r'(?:参见|引用|参考|基于)[^。，；]*?相关研究[^。，；]*?(?:20\d{2})',
        ]
        
        for pattern in fake_ref_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                risks.append(f"潜在幻觉：模糊引用的学术来源 '{match[:35]}...'")
        
        # 检测无作者信息的简单引用
        generic_refs = re.findall(r'(?:参见|引用|参考|基于)\s*(?:20\d{2})\s*(?:年)?\s*(?:的)?\s*(?:论文|研究|文献|报告)', text)
        for ref in generic_refs:
            risks.append(f"潜在幻觉：缺少作者信息的模糊引用 '{ref[:30]}...'")
        
        # 2. 数据编造检测
        fake_stats = re.findall(r'(?:准确率|精度|得分|分数|正确率)[：:]\s*(\d+\.?\d*)\s*[%分]', text)
        for score_str in fake_stats:
            try:
                score = float(score_str)
                if score > 99.9:
                    risks.append(f"数据可疑：过高精度 '{score}%' 需验证来源")
            except ValueError:
                pass
        
        # 3. 虚构方法检测
        if re.search(r'(?:全新方法|独创算法|革命性突破)[^。]*?(?:20\d{2})', text):
            risks.append("潜在幻觉：声称全新方法但缺乏具体信息")
        
        # 4. 无来源数据引用检测
        claim_count = len(re.findall(r'(?:研究表明|研究显示|数据表明|实验证明)', text))
        source_count = len(re.findall(r'(?:引用|参考|参见|根据)[^。，；]{0,30}(?:论文|研究|文献|报告)', text))
        if claim_count >= 2 and source_count == 0:
            risks.append("潜在幻觉：多次引用研究结论但未提供任何来源")
        
        return risks
    
    @classmethod
    def comprehensive_check(cls, text, subject='ai', context=None):
        """综合内容安全检查"""
        result = {'passed': True, 'issues': [], 'risk_level': 'low', 'details': {}}
        
        factual = cls.check_factual_accuracy(text, subject)
        sensitive = cls.check_sensitive_content(text)
        overpromise = cls.check_overpromise(text)
        hallucination = cls.check_hallucination_risk(text, context)
        
        result['details'] = {
            'factual_issues': factual,
            'sensitive_issues': sensitive,
            'overpromise_issues': overpromise,
            'hallucination_issues': hallucination
        }
        
        all_issues = sensitive + factual + overpromise + hallucination
        
        if sensitive:
            result['passed'] = False
            result['risk_level'] = 'reject'
        elif len(factual) >= 3 or len(hallucination) >= 2:
            result['passed'] = False
            result['risk_level'] = 'flag'
        elif factual or overpromise or hallucination:
            result['passed'] = True
            result['risk_level'] = 'warning'
        
        result['issues'] = all_issues
        return result
    
    @classmethod
    def sanitize_output(cls, text, subject='ai'):
        """净化输出 - 替换/移除问题内容"""
        check = cls.comprehensive_check(text, subject)
        if check['passed'] and check['risk_level'] == 'low':
            return text, check
        
        sanitized = text
        
        # 移除敏感内容（硬违规）
        for pattern, category in cls.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, '[内容已过滤]', sanitized, flags=re.IGNORECASE)
        
        # 弱化绝对化表述（软违规）
        sanitized = re.sub(r'(保证学会|保证掌握|保证通过)', '建议学习', sanitized)
        sanitized = re.sub(r'(确保学会|确保掌握|确保通过)', '建议掌握', sanitized)
        sanitized = re.sub(r'绝对([^不])', r'相对\1', sanitized)
        sanitized = re.sub(r'100%([^以])', r'较高\1', sanitized)
        sanitized = re.sub(r'(肯定[^不]|必定)', '可能', sanitized)
        
        return sanitized, check


# ================================================================
# 行为追踪 - 实时记录学习行为
# ================================================================
class BehaviorTracker:
    """学习行为实时追踪"""
    
    # 行为类型权重 - 不同学习行为对等级提升的贡献不同
    BEHAVIOR_WEIGHTS = {
        'assessment': 5,           # 测评：高权重
        'profile_complete': 5,     # 完成画像：高权重
        'resource_recommend': 2,   # 获取推荐资源
        'tutor': 3,                # 智能辅导问答
        'generate_resource': 3,    # 生成学习资源
        'resource_view': 1,        # 浏览资源
        'read_resource': 1,        # 阅读资源
        'watch_video': 1,          # 观看视频
        'do_exercise': 2,          # 做练习
        'ask_question': 2,         # 提问
    }
    
    # 学习积分 → 等级映射
    LEVEL_THRESHOLDS = [
        (0, 1),    # 0-14 分 → Level 1 基础
        (15, 2),   # 15-39 分 → Level 2 中等
        (40, 3),   # 40-79 分 → Level 3 高级
        (80, 4),   # 80+ 分 → Level 4 大神
    ]
    
    @staticmethod
    def log(user_id, subject, behavior_type, **kwargs):
        """记录一个学习行为，并自动更新用户画像等级"""
        behavior = LearningBehavior(
            user_id=user_id,
            subject=subject,
            behavior_type=behavior_type,
            resource_type=kwargs.get('resource_type'),
            resource_id=kwargs.get('resource_id'),
            detail=json.dumps(kwargs.get('detail', {}), ensure_ascii=False),
            score=kwargs.get('score'),
            time_spent=kwargs.get('time_spent'),
            completion=kwargs.get('completion'),
        )
        db.session.add(behavior)
        db.session.commit()
        
        # 自动重新计算并更新用户等级
        try:
            BehaviorTracker.recalculate_user_level(user_id, subject)
        except Exception:
            pass  # 等级更新失败不影响行为记录
        
        return behavior
    
    @staticmethod
    def calculate_learning_score(user_id, subject=None):
        """根据用户所有学习行为计算学习积分"""
        query = LearningBehavior.query.filter_by(user_id=user_id)
        if subject:
            query = query.filter_by(subject=subject)
        behaviors = query.all()
        
        total_score = 0
        for b in behaviors:
            weight = BehaviorTracker.BEHAVIOR_WEIGHTS.get(b.behavior_type, 1)
            # 完成度加成
            completion_bonus = 0
            if b.completion and b.completion > 0:
                completion_bonus = weight * (b.completion / 100.0) * 0.5
            # 分数加成
            score_bonus = 0
            if b.score and b.score > 0:
                score_bonus = (b.score / 100.0) * weight * 0.3
            total_score += weight + completion_bonus + score_bonus
        
        return round(total_score, 1)
    
    @staticmethod
    def score_to_level(score):
        """学习积分转等级"""
        for threshold, level in reversed(BehaviorTracker.LEVEL_THRESHOLDS):
            if score >= threshold:
                return level
        return 1
    
    @staticmethod
    def recalculate_user_level(user_id, subject=None):
        """重新计算用户等级并更新 LearningPlan
        
        等级只会上升不会下降（基于学习积累的递进模型）
        返回: (new_level, old_level, upgraded)
        """
        score = BehaviorTracker.calculate_learning_score(user_id, subject)
        new_level = BehaviorTracker.score_to_level(score)
        
        # 查找当前活跃的学习计划
        plan = LearningPlan.query.filter_by(
            user_id=user_id, is_active=True
        ).order_by(LearningPlan.updated_at.desc()).first()
        
        old_level = plan.current_level if plan else 1
        
        # 如果没有学习计划，创建一个
        if not plan:
            plan = LearningPlan(
                user_id=user_id,
                subject=subject or 'computer_science',
                is_active=True,
                current_level=new_level,
                target_level=min(new_level + 1, 4),
                started_at=datetime.utcnow(),
                adjustment_log=json.dumps([], ensure_ascii=False),
                resource_strategy=json.dumps([], ensure_ascii=False),
            )
            db.session.add(plan)
            db.session.commit()
            return (new_level, old_level, new_level > old_level)
        
        # 等级只会上升
        if new_level > old_level:
            plan.current_level = new_level
            plan.target_level = min(new_level + 1, 4)
            plan.updated_at = datetime.utcnow()
            
            # 记录调整日志
            try:
                log = json.loads(plan.adjustment_log) if plan.adjustment_log else []
            except Exception:
                log = []
            log.append({
                'type': 'level_upgrade',
                'from': old_level,
                'to': new_level,
                'score': score,
                'timestamp': datetime.utcnow().isoformat(),
                'reason': f'学习积分达到 {score}，自动升级'
            })
            plan.adjustment_log = json.dumps(log, ensure_ascii=False)
            db.session.commit()
            return (new_level, old_level, True)
        
        return (old_level, old_level, False)
    
    @staticmethod
    def get_user_behaviors(user_id, subject, days=30):
        """获取用户最近的行为数据"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return LearningBehavior.query.filter(
            LearningBehavior.user_id == user_id,
            LearningBehavior.subject == subject,
            LearningBehavior.created_at >= cutoff
        ).order_by(LearningBehavior.created_at).all()
    
    @staticmethod
    def analyze_behavior_stats(behaviors):
        """分析行为统计数据"""
        if not behaviors:
            return {}
        
        stats = {
            'total_actions': len(behaviors),
            'by_type': {},
            'by_resource': {},
            'avg_completion': 0,
            'total_study_time': 0,
            'active_days': set(),
            'score_history': [],
        }
        
        for b in behaviors:
            stats['by_type'][b.behavior_type] = stats['by_type'].get(b.behavior_type, 0) + 1
            if b.resource_type:
                stats['by_resource'][b.resource_type] = stats['by_resource'].get(b.resource_type, 0) + 1
            if b.completion:
                stats['avg_completion'] += b.completion
            if b.time_spent:
                stats['total_study_time'] += b.time_spent
            if b.score is not None:
                stats['score_history'].append({'score': b.score, 'date': b.created_at.strftime('%m-%d')})
            stats['active_days'].add(b.created_at.strftime('%Y-%m-%d'))
        
        total = len(behaviors)
        if total > 0:
            stats['avg_completion'] = round(stats['avg_completion'] / total, 1)
        
        stats['active_days'] = len(stats['active_days'])
        stats['avg_daily_actions'] = round(total / max(stats['active_days'], 1), 1)
        
        return stats


# ================================================================
# LLM评估 - 大模型驱动的多维度评估
# ================================================================
class LLMEvaluator:
    """利用LLM进行学生学习效果评估"""
    
    @staticmethod
    def build_eval_prompt(user_data, behavior_stats, subject_name, current_level):
        """构建评估提示词"""
        
        dims_desc = "\n".join([f"- {d['name']}（权重{d['weight']}）：{d['desc']}" for d in EVAL_DIMENSIONS])
        
        prompt = f"""你是一名教育评估专家，正在对一名学习「{subject_name}」的学生进行全面学习效果评估。

## 学生当前状态
- 当前学习层次：Level {current_level}
- 已完成的评估次数：{user_data.get('eval_count', 0)}
- 最近测评分数：{user_data.get('latest_assessment_score', '暂无')}
- 总学习行为记录数：{behavior_stats.get('total_actions', 0)}

## 行为数据分析
- 日均学习动作：{behavior_stats.get('avg_daily_actions', 0)}次
- 平均完成度：{behavior_stats.get('avg_completion', 0)}%
- 总学习时长：{behavior_stats.get('total_study_time', 0)}秒
- 活跃天数：{behavior_stats.get('active_days', 0)}天
- 各类型行为分布：{json.dumps(behavior_stats.get('by_type', {}), ensure_ascii=False)}

## 评估要求
请从以下5个维度评分（0-100分）：
{dims_desc}

## 输出格式（JSON ONLY，不要其他文字）
{{
    "dimension_scores": {{
        "knowledge": <0-100>,
        "understanding": <0-100>,
        "application": <0-100>,
        "analysis": <0-100>,
        "creativity": <0-100>
    }},
    "summary": "<根据数据分析的50-100字评估摘要，具体说明该生学习状态>",
    "strengths": ["<基于数据的优势1，具体说明>", "<基于数据的优势2>", "<基于数据的优势3>"],
    "weaknesses": ["<基于数据的短板1，具体说明>", "<基于数据的短板2>"],
    "recommendations": ["<可操作的建议1，具体到学科内容>", "<建议2>", "<建议3>"],
    "suggested_action": "<upgrade|stay|consolidate|customize>",
    "confidence": <0.0-1.0>
}}

评分依据：
- 知识掌握：基于测评成绩、完成度
- 理解深度：基于辅导对话质量、练习正确率
- 应用能力：基于练习完成情况、项目尝试
- 分析评价：基于多样化资源使用、错误分析
- 创新思维：基于主动探索行为、创新性问题

调级规则：
- upgrade（升级）：综合≥80且各维度≥70
- stay（保持）：综合50-80
- consolidate（巩固）：综合30-50或某维度严重偏低
- customize（个性化）：需要定制化方案
"""
        return prompt
    
    @staticmethod
    def evaluate_with_llm(prompt):
        """调用讯飞星火大模型进行真实LLM评估"""
        try:
            from llm_client import spark_chat
            system_msg = "你是一个教育评估专家，严格按JSON格式输出评估结果。不要输出JSON之外的任何文字。"
            result = spark_chat(system_msg, prompt, temperature=0.3, max_tokens=2048)
            return LLMEvaluator._parse_llm_response(result)
        except Exception as e:
            print(f"[LLMEvaluator] LLM调用失败: {e}")
            return None
    
    @staticmethod
    def _parse_llm_response(response):
        """解析LLM返回的JSON"""
        if not response:
            return None
        
        text = response
        # 尝试提取JSON
        json_match = re.search(r'\{[^{}]*"dimension_scores"[^{}]*\}', text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
        
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        return None
    
    @staticmethod
    def calculate_fallback_scores(behavior_stats, user_data):
        """LLM不可用时的回退评分算法 — 纯数据驱动，无随机"""
        behaviors = behavior_stats
        base_score = user_data.get('latest_assessment_score') or 60

        engagement_bonus = min(15, behaviors.get('total_actions', 0) * 0.3)
        completion_bonus = behaviors.get('avg_completion', 50) * 0.15
        diversity_bonus = min(10, len(behaviors.get('by_type', {})) * 2)

        adjusted = base_score + engagement_bonus + completion_bonus + diversity_bonus
        adjusted = min(100, max(0, adjusted))

        # 维度偏移因子 — 反映典型学习曲线：知识掌握最高，高阶思维最低
        dimension_skew = {
            'knowledge': 0,
            'understanding': -5,
            'application': -8,
            'analysis': -10,
            'creativity': -12,
            'self_learning': -4,
        }

        scores = {}
        for dim in EVAL_DIMENSIONS:
            skew = dimension_skew.get(dim['id'], 0)
            scores[dim['id']] = min(100, max(0, adjusted + skew))

        weighted = sum(scores[d['id']] * d['weight'] for d in EVAL_DIMENSIONS)

        # 评分阈值驱动调级
        min_dim = min(scores.values())
        if weighted >= 80 and min_dim >= 65:
            action = 'upgrade'
        elif weighted >= 50:
            action = 'stay'
        elif weighted >= 25:
            action = 'consolidate'
        else:
            action = 'customize'

        # 从维度分排序确定优缺点
        sorted_dims = sorted(EVAL_DIMENSIONS, key=lambda d: scores[d['id']], reverse=True)
        strengths = [f"{d['name']}表现较好（{int(scores[d['id']])}分）" for d in sorted_dims[:2] if scores[d['id']] >= 55]
        weaknesses = [f"{d['name']}需加强（{int(scores[d['id']])}分）" for d in sorted_dims[-2:] if scores[d['id']] < 55]

        recommendations = []
        weak_names = [d['name'] for d in sorted_dims[-2:] if scores[d['id']] < 55]

        if action == 'upgrade':
            recommendations.append("各维度表现均衡且达标，可以挑战更高层次的内容")
        elif action == 'stay':
            recommendations.append("保持当前学习节奏，重点关注短板维度")
        elif action == 'consolidate':
            recommendations.append("建议暂停推进新内容，集中巩固已有知识点")
            if weak_names:
                recommendations.append(f"优先巩固：{'、'.join(weak_names)}")
        else:
            recommendations.append("目前学习基础偏弱，建议制定针对性补强计划")

        if behaviors.get('avg_daily_actions', 0) < 3:
            recommendations.append(f"日均学习动作仅{int(behaviors.get('avg_daily_actions', 0))}次，建议增加学习频率")

        # 确定性拼接摘要
        daily = behaviors.get('avg_daily_actions', 0)
        completion = behaviors.get('avg_completion', 0)
        total = behaviors.get('total_actions', 0)

        action_label = {'upgrade': '可升级', 'stay': '保持当前', 'consolidate': '建议巩固', 'customize': '需定制方案'}

        summary_parts = [
            f"综合评分{int(round(weighted))}分，整体处于{'优秀' if weighted >= 75 else '良好' if weighted >= 55 else '需加强'}水平。"
        ]
        if total > 0:
            summary_parts.append(f"学习行为数据：日均{daily}次动作，平均完成度{int(completion)}%。")
        summary_parts.append(f"建议{action_label.get(action, '保持当前节奏')}。")

        return {
            'dimension_scores': scores,
            'summary': ''.join(summary_parts),
            'strengths': strengths or ['各维度表现均衡'],
            'weaknesses': weaknesses or ['无明显短板'],
            'recommendations': recommendations,
            'suggested_action': action,
            'confidence': round(min(0.8, 0.4 + len(behaviors.get('by_type', {})) * 0.05), 2),
        }
    
    @classmethod
    def full_evaluate(cls, user_id, subject, subject_name, current_level, user_data=None):
        """执行完整评估流程"""
        # 1. 获取行为数据
        behaviors = BehaviorTracker.get_user_behaviors(user_id, subject, days=30)
        behavior_stats = BehaviorTracker.analyze_behavior_stats(behaviors)
        
        if user_data is None:
            user_data = cls._get_user_data(user_id, subject)
        
        # 2. 尝试LLM评估
        prompt = cls.build_eval_prompt(user_data, behavior_stats, subject_name, current_level)
        result = cls.evaluate_with_llm(prompt)
        
        # 3. LLM不可用时回退到算法
        if not result:
            result = cls.calculate_fallback_scores(behavior_stats, user_data)
        
        # 4. 计算最终综合得分
        weighted = 0
        if 'dimension_scores' in result:
            weighted = sum(result['dimension_scores'].get(d['id'], 0) * d['weight'] for d in EVAL_DIMENSIONS)
        else:
            weighted = result.get('overall', 60)
        
        result['overall'] = round(weighted)
        
        # 5. 生成调整建议
        plan_adjustments = cls._generate_plan_adjustments(result, behavior_stats, current_level)
        resource_adjustments = cls._generate_resource_adjustments(result, subject)
        
        result['plan_adjustments'] = plan_adjustments
        result['resource_adjustments'] = resource_adjustments
        
        # 6. 安全过滤
        safety_check = SafetyFilter.comprehensive_check(
            json.dumps(result, ensure_ascii=False), 
            subject
        )
        result['safety_check'] = {
            'passed': safety_check['passed'],
            'issues': safety_check['issues'],
            'risk_level': safety_check['risk_level'],
        }
        
        # 7. 保存评估报告
        report = cls._save_report(user_id, subject, result, current_level)
        result['report_id'] = report.id
        
        return result
    
    @staticmethod
    def _get_user_data(user_id, subject):
        """获取用户数据"""
        assessments = Assessment.query.filter_by(
            user_id=user_id, subject=subject
        ).order_by(Assessment.created_at.desc()).all()
        
        data = {
            'eval_count': len(assessments),
            'latest_assessment_score': None,
        }
        
        if assessments:
            data['latest_assessment_score'] = assessments[0].total_score
        
        return data
    
    @staticmethod
    def _generate_plan_adjustments(result, behavior_stats, current_level):
        """生成学习计划调整建议"""
        action = result.get('suggested_action', 'stay')
        adjustments = []
        
        if action == 'upgrade':
            new_level = min(4, current_level + 1)
            adjustments.append({
                'type': 'level_change',
                'from': current_level,
                'to': new_level,
                'reason': f'综合评分{result["overall"]}分，各维度表现良好',
                'action': f'提升到Level {new_level}'
            })
            adjustments.append({
                'type': 'schedule',
                'action': '增加挑战性内容比例至60%',
                'detail': '推荐更多综合应用和项目型学习内容'
            })
        elif action == 'consolidate':
            adjustments.append({
                'type': 'review',
                'action': '暂停新内容，系统复习',
                'detail': f'重点加强{", ".join(result.get("weaknesses", ["薄弱环节"]))}',
                'frequency': '每3天一次小测'
            })
        elif action == 'customize':
            adjustments.append({
                'type': 'custom',
                'action': '生成个性化学习方案',
                'detail': '根据薄弱维度定制练习计划'
            })
        else:
            adjustments.append({
                'type': 'maintain',
                'action': '保持当前学习节奏',
                'detail': '每周增加一次综合练习'
            })
        
        # 根据活跃度调整
        daily = behavior_stats.get('avg_daily_actions', 0)
        if daily < 3:
            adjustments.append({
                'type': 'engagement',
                'action': '增加学习频率',
                'detail': f'当前日均{daily}次学习，建议提升到5次以上'
            })
        
        return adjustments
    
    @staticmethod
    def _generate_resource_adjustments(result, subject):
        """生成资源推送调整"""
        action = result.get('suggested_action', 'stay')
        weaknesses = result.get('weaknesses', [])
        
        adjustments = []
        
        # 基于薄弱维度推送
        for w in weaknesses[:3]:
            dim_id = None
            for d in EVAL_DIMENSIONS:
                if d['name'] in w:
                    dim_id = d['id']
                    break
            if dim_id:
                adjustments.append({
                    'type': 'weakness_focus',
                    'dimension': dim_id,
                    'strategy': f'针对{dim_id}推送基础巩固型资源',
                    'resource_types': ['document', 'quiz', 'tutorial_video']
                })
        
        # 基于动作调���推送
        if action == 'upgrade':
            adjustments.append({
                'type': 'challenge',
                'strategy': '推送高级应用和项目实战型资源',
                'resource_types': ['case_study', 'project', 'research_paper']
            })
        elif action in ('consolidate', 'customize'):
            adjustments.append({
                'type': 'foundation',
                'strategy': '推送基础概念讲解和入门练习',
                'resource_types': ['document', 'quiz', 'mindmap']
            })
        
        return adjustments
    
    @staticmethod
    def _save_report(user_id, subject, result, current_level):
        """保存评估报告到数据库"""
        dimension_scores = result.get('dimension_scores', {})
        
        # 计算目标级别
        action = result.get('suggested_action', 'stay')
        if action == 'upgrade':
            to_level = min(4, current_level + 1)
        elif action == 'consolidate':
            to_level = max(1, current_level - 1)
        else:
            to_level = current_level
        
        report = EvaluationReport(
            user_id=user_id,
            subject=subject,
            overall_score=result.get('overall', 0),
            dimension_scores=json.dumps(dimension_scores, ensure_ascii=False),
            confidence=result.get('confidence', 0.5),
            summary=result.get('summary', ''),
            strengths=json.dumps(result.get('strengths', []), ensure_ascii=False),
            weaknesses=json.dumps(result.get('weaknesses', []), ensure_ascii=False),
            recommendations=json.dumps(result.get('recommendations', []), ensure_ascii=False),
            suggested_action=action,
            from_level=current_level,
            to_level=to_level,
            plan_adjustments=json.dumps(result.get('plan_adjustments', []), ensure_ascii=False),
            resource_adjustments=json.dumps(result.get('resource_adjustments', []), ensure_ascii=False),
        )
        db.session.add(report)
        db.session.commit()
        return report


# ================================================================
# 异步任务进度追踪
# ================================================================
class ProgressTracker:
    """异步任务进度管理"""
    
    @staticmethod
    def create_task(user_id, task_type):
        task = AsyncTask(
            user_id=user_id,
            task_type=task_type,
            status='pending',
            progress=0.0,
            stage='初始化'
        )
        db.session.add(task)
        db.session.commit()
        return task.id
    
    @staticmethod
    def update_progress(task_id, progress, stage=None, status=None):
        task = AsyncTask.query.get(task_id)
        if not task:
            return
        task.progress = progress
        if stage:
            task.stage = stage
        if status:
            task.status = status
        if status == 'completed':
            task.completed_at = datetime.utcnow()
        db.session.commit()
    
    @staticmethod
    def complete_task(task_id, result=None):
        task = AsyncTask.query.get(task_id)
        if not task:
            return
        task.status = 'completed'
        task.progress = 100.0
        task.completed_at = datetime.utcnow()
        if result:
            task.result = json.dumps(result, ensure_ascii=False)
        db.session.commit()
    
    @staticmethod
    def fail_task(task_id, error):
        task = AsyncTask.query.get(task_id)
        if not task:
            return
        task.status = 'failed'
        task.error = str(error)
        db.session.commit()
    
    @staticmethod
    def get_task(task_id):
        task = AsyncTask.query.get(task_id)
        if not task:
            return None
        return {
            'id': task.id,
            'type': task.task_type,
            'status': task.status,
            'progress': task.progress,
            'stage': task.stage,
            'result': json.loads(task.result) if task.result else None,
            'error': task.error,
        }


# ================================================================
# 动态计划优化器
# ================================================================
class PlanOptimizer:
    """基于评估结果动态优化学习计划（含跨Agent协作反馈回路）"""
    
    @staticmethod
    def update_learning_plan(user_id, subject, eval_result, current_level):
        """根据评估结果更新学习计划"""
        # 查找或创建计划
        plan = LearningPlan.query.filter_by(
            user_id=user_id, subject=subject, is_active=True
        ).first()
        
        if not plan:
            plan = LearningPlan(
                user_id=user_id,
                subject=subject,
                current_level=current_level,
                target_level=min(4, current_level + 1),
                plan_data=json.dumps({'version': 1}, ensure_ascii=False),
                feedback_loop=json.dumps([], ensure_ascii=False),
            )
            db.session.add(plan)
        
        # 更新级别
        new_level = eval_result.get('to_level', current_level)
        plan.current_level = new_level
        plan.resource_strategy = json.dumps(
            eval_result.get('resource_adjustments', []), 
            ensure_ascii=False
        )
        
        # 记录调整日志
        adjustment_log = []
        if plan.adjustment_log:
            try:
                adjustment_log = json.loads(plan.adjustment_log)
            except (json.JSONDecodeError, TypeError):
                adjustment_log = []
        
        adjustment_log.append({
            'date': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
            'action': eval_result.get('suggested_action', 'stay'),
            'from_level': current_level,
            'to_level': new_level,
            'overall_score': eval_result.get('overall', 0),
            'reason': eval_result.get('summary', '')[:100],
        })
        
        plan.adjustment_log = json.dumps(adjustment_log, ensure_ascii=False)
        
        # ==================== 跨Agent协作反馈回路 ====================
        # 1. 判断评估建议方向
        suggested_action = eval_result.get('suggested_action', 'stay')
        suggestion = 'maintain'
        if suggested_action == 'upgrade':
            suggestion = 'upgrade'
        elif suggested_action == 'downgrade':
            suggestion = 'downgrade'
        
        # 2. 验证之前的反馈记录（闭环验证）
        PlanOptimizer._verify_feedback_loop(plan, new_level, eval_result.get('overall', 0))
        
        # 3. 如果有新的升级/降级建议，记录新的反馈条目
        if suggestion != 'maintain':
            PlanOptimizer._record_feedback_entry(plan, suggestion, new_level)
        
        db.session.commit()
        return plan
    
    @staticmethod
    def _record_feedback_entry(plan, suggestion, suggested_level):
        """记录新的反馈条目（评估建议）"""
        feedback_loop = []
        if plan.feedback_loop:
            try:
                feedback_loop = json.loads(plan.feedback_loop)
            except (json.JSONDecodeError, TypeError):
                feedback_loop = []
        
        feedback_loop.append({
            'evaluation_id': plan.last_evaluation_id or 0,
            'suggestion': suggestion,
            'suggested_level': suggested_level,
            'suggested_at': datetime.utcnow().isoformat(),
            'verify_at': None,
            'verify_score': None,
            'verify_level': None,
            'effect': None,
            'days_to_verify': None,
            'status': 'pending'
        })
        
        plan.feedback_loop = json.dumps(feedback_loop, ensure_ascii=False)
    
    @staticmethod
    def _verify_feedback_loop(plan, current_level, current_score):
        """验证之前未完成的反馈记录（闭环验证）
        
        当新的评估结果出来时，检查是否有之前的升级/降级建议需要验证
        如果建议升级后实际等级提升了，说明建议有效；否则说明需要调整策略
        """
        if not plan.feedback_loop:
            return
        
        try:
            feedback_loop = json.loads(plan.feedback_loop)
        except (json.JSONDecodeError, TypeError):
            return
        
        for entry in feedback_loop:
            if entry.get('status') == 'pending' and entry.get('suggested_at'):
                # 计算建议到验证的天数
                suggested_time = datetime.fromisoformat(entry['suggested_at'])
                verify_time = datetime.utcnow()
                days_to_verify = (verify_time - suggested_time).days
                
                # 判断效果
                effect = 'stable'
                suggested_level = entry.get('suggested_level', 0)
                
                if suggested_level < current_level:
                    effect = 'improved'
                elif suggested_level > current_level:
                    effect = 'declined'
                
                # 更新反馈记录
                entry.update({
                    'verify_at': verify_time.isoformat(),
                    'verify_score': current_score,
                    'verify_level': current_level,
                    'effect': effect,
                    'days_to_verify': days_to_verify,
                    'status': 'verified'
                })
        
        plan.feedback_loop = json.dumps(feedback_loop, ensure_ascii=False)
    
    @staticmethod
    def get_feedback_summary(plan):
        """获取反馈回路总结报告"""
        if not plan.feedback_loop:
            return {
                'total_suggestions': 0,
                'verified_count': 0,
                'pending_count': 0,
                'effect_stats': {'improved': 0, 'declined': 0, 'stable': 0},
                'average_days_to_verify': 0,
                'conclusion': '暂无反馈数据'
            }
        
        try:
            feedback_loop = json.loads(plan.feedback_loop)
        except (json.JSONDecodeError, TypeError):
            return {'error': '解析反馈数据失败'}
        
        verified = [e for e in feedback_loop if e.get('status') == 'verified']
        pending = [e for e in feedback_loop if e.get('status') == 'pending']
        
        effect_stats = {'improved': 0, 'declined': 0, 'stable': 0}
        total_days = 0
        
        for entry in verified:
            effect = entry.get('effect', 'stable')
            effect_stats[effect] += 1
            if entry.get('days_to_verify'):
                total_days += entry['days_to_verify']
        
        avg_days = round(total_days / len(verified), 1) if verified else 0
        
        # 生成结论
        if len(verified) >= 3:
            improvement_rate = effect_stats['improved'] / len(verified) * 100
            if improvement_rate >= 60:
                conclusion = f'评估建议有效率{improvement_rate:.0f}%，升级建议整体推动了学习进步'
            elif improvement_rate >= 40:
                conclusion = f'评估建议有效率{improvement_rate:.0f}%，部分建议效果显著'
            else:
                conclusion = f'评估建议有效率{improvement_rate:.0f}%，需要优化评估策略'
        else:
            conclusion = f'已验证{len(verified)}条反馈，数据积累中'
        
        return {
            'total_suggestions': len(feedback_loop),
            'verified_count': len(verified),
            'pending_count': len(pending),
            'effect_stats': effect_stats,
            'average_days_to_verify': avg_days,
            'conclusion': conclusion,
            'recent_feedbacks': verified[-3:] if verified else []
        }
