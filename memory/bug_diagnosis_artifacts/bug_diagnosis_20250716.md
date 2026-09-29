# Bug诊断报告：四个核心功能缺陷

## 问题0：全局根因 — LLM不可用时的降级逻辑缺陷

所有四个bug的共性根因是：**LLM调用失败后，降级逻辑要么产生垃圾数据，要么执行逻辑错误**。系统各模块对LLM调用失败的容错方式不一致：

| 模块 | LLM降级策略 | 结果 |
|------|------------|------|
| AssessmentAgent.evaluate() | 用accuracy + random偏移量 | 得分在accuracy附近浮动，勉强可用 |
| ProfilingAgent.analyze_assessment() | 用raw_avg（自评分数） | 返回用户自评值，不准确但可区分 |
| TutorAgent | **无降级** → 调用失败直接返回异常 | 空响应/错误 |
| LLMEvaluator.full_evaluate() | `calculate_fallback_scores()` | 返回确定性评分，有数据无问题 |
| path_planning_agent | 检查用户画像/测评数据 | 逻辑闸门有bug |

---

## 问题1：评分结果不区分回答

**表面症状**：AI对所有问题给出相同评分。

**根因**：`AssessmentAgent.evaluate()` 在第31-40行的LLM降级中：

```python
dimension_scores = {
    "knowledge": min(100, accuracy + random.randint(-5, 5)),
    "understanding": min(100, accuracy + random.randint(-10, 5)),
    "application": min(100, accuracy + random.randint(-10, 5)),
    "analysis": min(100, accuracy + random.randint(-10, 10)),
    "creativity": min(100, accuracy + random.randint(-5, 10)),
}
```

所有维度以 `accuracy`（整体正确率）为中心做 ±10 内的随机抖动。如果用户答了10题对8题，accuracy=80%，五个维度得分都在 70-90 之间打转，**看不出每题之间的区别**。这不是逐题评分，是按整体正确率算总分再分到维度上的。

另外，如果LLM成功调用，`AssessmentAgent.evaluate()` 的prompt也只传了整体正确率 `accuracy`，没有逐题作答质量分析——LLM同样无法区分每题差异。

**修正方向**：逐题评分，每个答案独立调用LLM评估，或者把逐题作答内容和LLM评分要求塞进prompt里，让LLM先评每题再汇总维度分。

---

## 问题2：路径模块要求"入学测评"，但画像已等同于测评

**表面症状**：已完成画像（Profile Builder）后，路径规划页面仍提示"请先完成入学测评"。

**根因**：`app.py` 第67-68行检查 `Assessment` 表是否有记录：

```python
if Assessment.query.filter_by(user_id=uid).first():
    completed.append('assessment')
```

但 `Assessment` 表只在 第810行的 `api_submit_assessment` 路由中写入——而这个路由对应的是**入学测评**，不是画像对话（ProfileConversation）。画像阶段产生的数据存在 `ProfileConversation` 表和 `LearningBehavior` 表中，不走 `Assessment` 表。

有两种可能：
1. 如果"入学测评"指的是 `api_submit_assessment` 对应的那个选择题测评，那确实是独立环节，路径模块的检查逻辑没问题，但用户画像流程的设计有问题——让学生以为画像等于测评。
2. 如果"入学测评"应该就是画像对话的产物，那路径模块就应该检查 `ProfileConversation` 或画像产生的能力维表，而不是 `Assessment`。

**修正方向**：在路径模块的检查中增加对画像完成的判断——检查 `ProfileConversation` 中是否有最近有效记录，或者将画像结果写入 `Assessment` 表的兼容字段。

---

## 问题3：辅导回答不区分问题

**表面症状**：无论学生问什么，辅导Agent给出相同答案。

**根因**：`TutorAgent` 继承自 `BaseAgent`（或类似基类），其对话接口在LLM调用失败时**无任何降级逻辑**。当讯飞API不可用时：

1. `call_llm()` / `spark_chat()` 抛出异常
2. 上层没有 `try/except` 包裹
3. 返回的是某个兜底空字符串，前端看到的就是空白或"我在思考..."
4. 如果重复问，每次LLM都失败，每次都返回空白，看起来就像"相同的空回答"

即使LLM可用，也要检查 `tutor_agent.py` 中是否将历史对话传入了prompt——如果没传，每次都是独立的单轮对话，且 prompt 中没有用户问题，LLM自然会给出相似的默认回答。

**修正方向**：第一，加 `try/except` 降级逻辑。第二，确认对话历史传入prompt。第三，确认LLM调用参数中 `temperature` 不是0（否则输出会高度一致）。

---

## 问题4：评估页面缺少内容

**表面症状**：维度表、优势/薄弱/建议、计划调整、进步趋势全部为空。

**根因**：前端的 `loadLatestReport()`（页面加载时调用）请求 `/api/evaluate/report`，该接口返回的数据集**不完整**：

```python
# evaluate_bp.py api_latest_report 返回的字段
return jsonify({
    'overall_score': ...,
    'dimension_scores': ...,
    'weaknesses': ...,
    'strengths': ...,
    'summary': ...,
    'recommendations': ...,
    # ⚠ 缺少 plan_adjustments, resource_adjustments, safety_check, level_change 等字段
})
```

前端的 `displayResult()` 会调用：
```javascript
renderPlanAdjustments(result);     // result.plan_adjustments → undefined → 显示"暂无调整建议"
renderResourceStrategy(result.resource_adjustments || []);  // undefined → 显示"暂无策略调整"
renderLevelChange(result);          // result.from_level/to_level → undefined
renderSafetyCheck(result.safety_check); // undefined
```

另外 `loadLatestReport()` 只调用一次不重试，如果请求失败（网络错误、5xx），`.catch(() => {})` 静默吞掉错误。

V2评估（通过 `startEvalV2()` 启动）用task轮询拿完整结果，所以V2运行后的结果显示正常——`plan_adjustments`、`safety_check` 等字段都从 `AsyncTask.result` 完整传来。但页面的**首次加载**用的是不完整的report接口。

**修正方向**：在 `api_latest_report` 的返回中加上 `plan_adjustments`、`resource_adjustments`、`from_level`、`to_level`、`safety_check` 等字段，或者干脆让加载最新报告时也走 `_save_report` 生成的完整数据返回。
