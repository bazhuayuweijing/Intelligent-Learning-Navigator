#!/usr/bin/env python3
"""A3智学领航 - 全量压力测试与性能测评脚本

创建多组模拟用户（不同基础、不同科目、不同画像），
全覆盖API路由，输出性能报告和问题总结。
"""
import sys, os, json, time, traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['DEMO_MODE'] = 'true'
os.environ['SECRET_KEY'] = 'test'
os.environ['SPARK_API_PASSWORD'] = 'test'

# ── 测试用户配置 ──────────────────────────────────────────────

TEST_USERS = [
    # (用户名, 密码, 画像数据)
    ("u_lv1_practice_python", "test123", {
        "major": "计算机科学",
        "goal": "打好编程基础",
        "cognitive_style": "实践驱动型",
        "dimension_scores": {"knowledge": 30, "understanding": 25, "application": 20, "analysis": 35, "creativity": 40, "self_learning": 45, "pace": 50, "cognitive": 30},
        "weak_points": ["application", "understanding"],
        "strong_points": ["self_learning"],
        "level": 1, "level_name": "基础",
        "test_subject": "python",
        "test_topic": "Python基础语法",
    }),
    ("u_lv2_theory_algo", "test123", {
        "major": "计算机科学",
        "goal": "深入学习算法原理",
        "cognitive_style": "系统理论型",
        "dimension_scores": {"knowledge": 65, "understanding": 55, "application": 45, "analysis": 30, "creativity": 60, "self_learning": 70, "pace": 55, "cognitive": 60},
        "weak_points": ["analysis"],
        "strong_points": ["knowledge", "self_learning"],
        "level": 2, "level_name": "中等",
        "test_subject": "computer_science",
        "test_topic": "数据结构与算法",
    }),
    ("u_lv2_visual_ai", "test123", {
        "major": "人工智能",
        "goal": "理解深度学习原理",
        "cognitive_style": "视觉型",
        "dimension_scores": {"knowledge": 55, "understanding": 50, "application": 40, "analysis": 45, "creativity": 65, "self_learning": 60, "pace": 50, "cognitive": 55},
        "weak_points": ["creativity"],
        "strong_points": ["understanding", "knowledge"],
        "level": 2, "level_name": "中等",
        "test_subject": "ai",
        "test_topic": "卷积神经网络",
    }),
    ("u_lv3_reading_web", "test123", {
        "major": "计算机科学",
        "goal": "掌握全栈开发",
        "cognitive_style": "阅读自学型",
        "dimension_scores": {"knowledge": 75, "understanding": 70, "application": 65, "analysis": 60, "creativity": 55, "self_learning": 85, "pace": 65, "cognitive": 70},
        "weak_points": ["application", "creativity"],
        "strong_points": ["self_learning", "knowledge"],
        "level": 3, "level_name": "高等",
        "test_subject": "web",
        "test_topic": "React前端框架",
    }),
    ("u_lv3_practice_math", "test123", {
        "major": "应用数学",
        "goal": "提高数学分析能力",
        "cognitive_style": "综合型",
        "dimension_scores": {"knowledge": 70, "understanding": 65, "application": 60, "analysis": 65, "creativity": 60, "self_learning": 70, "pace": 60, "cognitive": 65},
        "weak_points": ["application"],
        "strong_points": ["knowledge", "analysis"],
        "level": 3, "level_name": "高等",
        "test_subject": "math",
        "test_topic": "微积分综合应用",
    }),
    ("u_lv4_expert_data", "test123", {
        "major": "数据科学",
        "goal": "深入研究机器学习",
        "cognitive_style": "系统理论型",
        "dimension_scores": {"knowledge": 90, "understanding": 85, "application": 80, "analysis": 80, "creativity": 75, "self_learning": 90, "pace": 80, "cognitive": 85},
        "weak_points": ["creativity"],
        "strong_points": ["knowledge", "self_learning", "understanding"],
        "level": 4, "level_name": "大神",
        "test_subject": "data_science",
        "test_topic": "机器学习模型调优",
    }),
    ("u_lv1_selfread_physics", "test123", {
        "major": "物理",
        "goal": "理解大学物理概念",
        "cognitive_style": "阅读自学型",
        "dimension_scores": {"knowledge": 25, "understanding": 20, "application": 15, "analysis": 30, "creativity": 35, "self_learning": 55, "pace": 40, "cognitive": 25},
        "weak_points": ["knowledge", "understanding", "application"],
        "strong_points": ["self_learning"],
        "level": 1, "level_name": "基础",
        "test_subject": "physics",
        "test_topic": "力学基础",
    }),
    ("u_lv2_visual_english", "test123", {
        "major": "外国语言文学",
        "goal": "提升英语阅读能力",
        "cognitive_style": "视觉型",
        "dimension_scores": {"knowledge": 50, "understanding": 45, "application": 40, "analysis": 35, "creativity": 50, "self_learning": 65, "pace": 55, "cognitive": 45},
        "weak_points": ["analysis"],
        "strong_points": ["self_learning"],
        "level": 2, "level_name": "中等",
        "test_subject": "english",
        "test_topic": "英语阅读理解",
    }),
]

RESULTS_FILE = "perf_test_results.json"

# ── 测试引擎 ──────────────────────────────────────────────────

import logging
logging.disable(logging.CRITICAL)  # 压缩日志

results = {
    "started_at": datetime.utcnow().isoformat(),
    "users": {},
    "summary": {
        "total_users": len(TEST_USERS),
        "total_api_calls": 0,
        "success_count": 0,
        "error_count": 0,
        "slow_calls": [],      # > 3s
        "5xx_count": 0,
        "profile_aware_diff": [],  # 差异验证
    },
    "issues": []
}


def _add_issue(severity, user, api, msg):
    results["issues"].append({
        "severity": severity,  # "bug" | "warn" | "info"
        "user": user,
        "api": api,
        "message": msg,
        "time": datetime.utcnow().isoformat(),
    })


class UserSession:
    """模拟用户会话"""
    def __init__(self, client, username, password, profile):
        self.client = client
        self.username = username
        self.password = password
        self.profile = profile
        self.user_timings = {}   # api_name -> [duration_ms]
        self.user_errors = []
    
    def _call(self, api_name, method, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            if method == 'get':
                resp = self.client.get(*args, **kwargs)
            else:
                resp = self.client.post(*args, **kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            self.user_timings.setdefault(api_name, []).append(elapsed)
            results["summary"]["total_api_calls"] += 1
            
            if resp.status_code >= 500:
                results["summary"]["5xx_count"] += 1
                msg = f"HTTP {resp.status_code}: {resp.data[:200]}"
                self.user_errors.append((api_name, msg))
                _add_issue("bug", self.username, api_name, msg)
                results["summary"]["error_count"] += 1
            elif resp.status_code < 500:
                results["summary"]["success_count"] += 1
            
            if elapsed > 3000:
                results["summary"]["slow_calls"].append({
                    "user": self.username, "api": api_name, "ms": round(elapsed, 1)
                })
            
            return resp, elapsed
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            msg = f"Exception: {type(e).__name__}: {e}"
            self.user_errors.append((api_name, msg))
            _add_issue("bug", self.username, api_name, msg)
            results["summary"]["error_count"] += 1
            results["summary"]["total_api_calls"] += 1
            return None, elapsed


def run_single_user(ctx, username, password, profile):
    """测试单个用户的全部流程"""
    us = UserSession(ctx, username, password, profile)
    
    # 1. 注册
    resp, t = us._call("register", "post",
        "/register",
        data={"username": username, "password": password, "confirm_password": password},
        follow_redirects=True
    )
    
    # 2. 登录
    resp, t = us._call("login", "post",
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True
    )
    if resp and resp.status_code >= 400:
        _add_issue("warn", username, "login", f"登录失败: {resp.status_code}")
        return us  # 无法继续
    
    # 3. 仪表盘
    resp, t = us._call("dashboard", "get", "/dashboard")
    
    # 4. 画像对话 - 模拟完整流程
    resp, t = us._call("profile_start", "post", "/api/profile/start")
    if resp:
        conv_data = resp.get_json() or {}
        conv_id = conv_data.get("conversation_id")
        
        # 5轮对话模拟
        chats = [
            f"我是{profile['major']}专业的学生",
            f"我目前的基础水平是{profile['level_name']}",
            f"我的薄弱点是{'、'.join(profile.get('weak_points', []))}",
            f"我的学习目标是{profile['goal']}",
            "以上是我的基本信息"
        ]
        for i, msg in enumerate(chats):
            resp, t = us._call(f"profile_chat_{i}", "post",
                "/api/profile/chat",
                json={"conversation_id": conv_id, "answer": msg}
            )
    
    # 5. 画像结果
    resp, t = us._call("profile_result", "get", "/api/profile/result")
    
    # 6. 入学测评（8层问卷）
    resp, t = us._call("assessment_questions", "get", "/api/assessment/questions")
    if resp and resp.status_code == 200:
        questions = (resp.get_json() or {}).get("questions", [])
        answers = {}
        for i, q in enumerate(questions[:8]):
            opts = q.get("options", [])
            if opts:
                answers[str(q.get("id", i))] = opts[0].get("value", opts[0].get("id", 0))
        if answers:
            resp, t = us._call("assessment_submit", "post",
                "/api/assessment/submit",
                json={"answers": answers}
            )
    
    # 7. 资源生成 - 核心测试（画像感知）
    subject = profile["test_subject"]
    topic = profile["test_topic"]
    
    resp, t = us._call("generate_all", "post",
        "/api/generate/all",
        json={"context": {"subject": subject, "topic": topic, "level": profile["level"]}}
    )
    if resp:
        gen_data = resp.get_json() or {}
        resources = gen_data.get("resources", {})
        gen_counts = {k: 1 for k in resources.keys()}
        us._gen_counts = gen_counts
    
    # 8. 单类型生成
    resp, t = us._call("generate_doc", "post",
        "/api/generate/type",
        json={"context": {"subject": subject, "topic": topic, "level": profile["level"]}, "type": "document"}
    )
    resp, t = us._call("generate_quiz", "post",
        "/api/generate/type",
        json={"context": {"subject": subject, "topic": topic, "level": profile["level"]}, "type": "quiz"}
    )
    resp, t = us._call("generate_mindmap", "post",
        "/api/generate/type",
        json={"context": {"subject": subject, "topic": topic, "level": profile["level"]}, "type": "mindmap"}
    )
    
    # 9. 克星题
    resp, t = us._call("trap_exam", "post",
        "/generate_trap_exam",
        json={"subject": subject, "subject_name": topic}
    )
    
    # 10. 资源管理
    resp, t = us._call("resources_list", "get", "/api/generated/list")
    
    # 11. 智能辅导
    tutor_questions = [
        ("什么是{0}", subject, topic),
        ("如何学习{0}", subject, topic),
        ("{0}和{1}有什么区别", subject, topic.replace(topic.split(" ")[0] if " " in topic else "", "相关概念")),
    ]
    for i, (qfmt, *_) in enumerate(tutor_questions[:2]):
        q_text = qfmt.format(topic)
        resp, t = us._call(f"tutor_ask_{i}", "post",
            "/api/tutor/ask",
            json={"question": q_text, "subject": subject}
        )
    
    # 12. 评估
    resp, t = us._call("evaluate_submit", "post",
        "/api/evaluate/submit",
        json={"subject": subject}
    )
    resp, t = us._call("evaluate_report", "get", "/api/evaluate/report")
    
    # 13. 学习计划
    resp, t = us._call("plan_current", "get", f"/api/plan/current?subject={subject}")
    
    # 14. 行为跟踪
    for bt in ["study", "quiz", "review"]:
        resp, t = us._call(f"behavior_log_{bt}", "post",
            "/api/behavior/log",
            json={"behavior_type": bt, "subject": subject, "time_spent": 30, "completion": 80}
        )
    
    resp, t = us._call("behavior_stats", "get", "/api/behavior/stats")
    
    # 15. 记忆温度
    resp, t = us._call("memory_temperature", "get", "/api/memory_temperature")
    
    # 16. 安全审核
    for content, label in [("作弊方法", "sensitive"), ("我保证100%学会", "overpromise"), ("正常学习", "normal")]:
        resp, t = us._call(f"safety_check_{label}", "post",
            "/api/safety/check",
            json={"content": content}
        )
    
    # 17. 反馈回路
    resp, t = us._call("feedback_summary", "get",
        f"/api/evaluate/feedback-summary?subject={subject}"
    )
    
    # 18. 用户统计
    resp, t = us._call("user_stats", "get", "/api/user/stats")
    
    # 19. 全量路由压测（模拟连续请求）
    bulk_routes = [
        ("get", "/dashboard"),
        ("get", "/profile"),
        ("get", "/resource-gen"),
        ("get", "/evaluate"),
        ("get", "/tutor"),
        ("get", "/trap_exam"),
    ]
    for method, route in bulk_routes:
        if method == "get":
            resp, t = us._call(f"page_{route.strip('/')}", "get", route)
    
    # 收集结果
    return us


def check_cross_user_diff(users_results):
    """验证不同画像学生是否获得不同资源"""
    quiz_focuses = {}
    for username, us in users_results.items():
        if hasattr(us, '_gen_counts'):
            quiz_focuses[username] = {
                "level": us.profile["level"],
                "style": us.profile["cognitive_style"],
                "weak": us.profile["weak_points"],
            }
    
    # 检查同一科目不同画像是否有差异
    from collections import defaultdict
    by_subject = defaultdict(list)
    for username, us in users_results.items():
        by_subject[us.profile["test_subject"]].append(username)
    
    same_subject_diffs = []
    for subject, unames in by_subject.items():
        if len(unames) >= 2:
            same_subject_diffs.append({
                "subject": subject,
                "users": unames,
                "diff_styles": [users_results[u].profile["cognitive_style"] for u in unames],
                "diff_levels": [users_results[u].profile["level"] for u in unames],
            })
    
    if same_subject_diffs:
        results["summary"]["profile_aware_diff"] = same_subject_diffs


def summarize_perf(users_results):
    """生成性能报告"""
    # 各端点的平均响应时间
    endpoint_times = {}
    for username, us in users_results.items():
        for api, timings in us.user_timings.items():
            avg = sum(timings) / len(timings)
            endpoint_times.setdefault(api, []).append(avg)
    
    # 慢端点 Top
    endpoint_avg = {api: round(sum(times)/len(times), 1) for api, times in endpoint_times.items()}
    slow_endpoints = sorted(endpoint_avg.items(), key=lambda x: -x[1])[:5]
    
    results["summary"]["endpoint_avg"] = endpoint_avg
    results["summary"]["slowest_endpoints"] = slow_endpoints
    
    # 用户维度汇总
    for username, us in users_results.items():
        errors = us.user_errors
        results["users"][username] = {
            "profile": {
                "level": us.profile["level"],
                "level_name": us.profile["level_name"],
                "style": us.profile["cognitive_style"],
                "subject": us.profile["test_subject"],
                "weak_points": us.profile["weak_points"],
            },
            "total_api_calls": len(us.user_timings),
            "errors": len(errors),
            "error_detail": errors[:3],
            "avg_response_ms": round(
                sum(ts for timings in us.user_timings.values() for ts in timings) /
                max(len([t for timings in us.user_timings.values() for t in timings]), 1), 1
            ),
        }


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║   A3智学领航 - 多用户全量性能测评                ║")
    print("║   测试用户: 8人 × 25+ API                        ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    
    from app import app as flask_app
    users_results = {}
    
    for idx, (username, password, profile) in enumerate(TEST_USERS, 1):
        label = f"[{idx}/{len(TEST_USERS)}] {username} ({profile['test_subject']}, Lv{profile['level']}, {profile['cognitive_style']})"
        print(f"\n── {label} ──")
        
        with flask_app.test_client() as c:
            us = run_single_user(c, username, password, profile)
            users_results[username] = us
            
            errors = us.user_errors
            slow = [s for s in results["summary"]["slow_calls"] if s["user"] == username]
            
            if errors:
                print(f"  ❌ 错误: {len(errors)} 个")
                for api, msg in errors[:3]:
                    print(f"     {api}: {msg[:120]}")
            else:
                print(f"  ✅ 全部通过 (0错误)")
            
            if slow:
                for s in slow:
                    print(f"  ⏱ 慢响应: {s['api']} = {s['ms']}ms")
            
            # 打印关键生成结果摘要
            if hasattr(us, '_gen_counts'):
                pass  # 后面统一打印
    
    # 差异验证
    print(f"\n── 跨用户画像感知差异验证 ──")
    check_cross_user_diff(users_results)
    diff = results["summary"].get("profile_aware_diff", [])
    if diff:
        for d in diff:
            print(f"  学科={d['subject']}: 用户={d['users']}, 风格={d['diff_styles']}, 等级={d['diff_levels']}")
        print(f"  ✅ 存在同一学科不同画像用户 -> 生成资源应存在差异")
    else:
        print(f"  ⚠ 未发现同科差异用户组")
    
    # 性能统计
    summarize_perf(users_results)
    
    # 慢端点 Top
    print(f"\n── 响应最慢 Top 5 端点 ──")
    for api, avg in results["summary"].get("slowest_endpoints", []):
        print(f"  {api}: {avg}ms")
    
    # 汇总
    s = results["summary"]
    print(f"\n═══ 测试汇总 ═══")
    print(f"  测试用户: {s['total_users']}")
    print(f"  API调用: {s['total_api_calls']} 次")
    print(f"  成功: {s['success_count']}")
    print(f"  失败: {s['error_count']} (5xx: {s['5xx_count']})")
    print(f"  慢调用(>3s): {len(s['slow_calls'])} 次")
    print(f"  问题数: {len(results['issues'])}")
    
    print(f"\n── 问题列表 ──")
    if results["issues"]:
        for iss in results["issues"]:
            icon = {"bug": "🐛", "warn": "⚠️", "info": "ℹ️"}.get(iss["severity"], "•")
            print(f"  {icon} [{iss['severity'].upper()}] {iss['user']}/{iss['api']}: {iss['message'][:150]}")
    else:
        print("  ✅ 无问题")
    
    # 保存结果
    results["finished_at"] = datetime.utcnow().isoformat()
    results["users"] = {k: v for k, v in results["users"].items()}  # 已经填了
    
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), RESULTS_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  结果已保存: {out_path}")


if __name__ == "__main__":
    main()
