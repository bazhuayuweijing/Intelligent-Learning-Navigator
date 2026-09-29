# 修复摘要 2026-07-14

## 修复 1: Python学科Mock数据缺失 → 文档和案例内容空泛

**根因**：`mock_data.py`的`MOCK_RESOURCES`字典中缺少"python"学科条目。当用户选择"Python编程"学科并请求资源时，系统回退到"computer_science"，返回"数据结构完整教程"等不相关的内容。

**方案**：
1. 在`MOCK_RESOURCES`中新增"python"条目，包含：
   - $docsPython编程完整教程（897字，含基础语法、进阶特性、常用库、最佳实践4章）
   - 知识导图Mermaid代码
   - 5道练习题（选择/填空/编程题）
   - 2个实操案例（成绩管理系统、Web爬虫）
   - 多媒体推荐资源（官方教程、PEP 8、从入门到实践等）

2. 修复`_get_mock_resource`函数中字段键名不一致的问题：
   - 原代码使用`"quizzes"`作为字段键，而补入的Python数据使用`"quiz"`，导致Python资源的题目查询始终回退到computer_science
   - `resource_map`中"quiz"映射到`("quizzes", default_subject["quizzes"])`，但get失败后无二级备选
   - 修复：将Python数据的"quiz"→"quizzes"统一，并在`_get_mock_resource`增加对"quiz"字段的fallback

3. `config.py`中`SUBJECTS`已包含"python"→"Python编程"映射

**影响文件**：mock_data.py（新增Python条目）、config.py（已有映射）

## 修复 2: 语音输入按钮VOICE_ENABLED始终为false

**根因**：Jinja2模板中`{% set voice_enabled = True %}`位于`{% block content %}`内，而引用该变量的JS代码位于另一个独立的`{% block extra_js %}`中。Jinja2的`{% set %}`仅在当前块作用域内可见，跨块不可见。

**修复**：在`{% block extra_js %}`中增加`{% set voice_enabled = True %}`，确保JS代码块能正确获取变量值。

**影响文件**：templates/tutor.html（在extra_js块中加入set语句）

## 验证结果

| 测试项 | 结果 |
|--------|------|
| Python学科文档生成 | ✅ 返回Python编程完整教程（897字） |
| Python导图生成 | ✅ Mermaid代码正确 |
| Python题目生成 | ✅ 返回Python相关题目 |
| Python案例生成 | ✅ 含Python代码提示 |
| 语音输入VOICE_ENABLED | ✅ const VOICE_ENABLED = true |
| STT降级接口 | ✅ 无API时返回模拟文本 |
| 学习资源生成 | ✅ 6种资源类型全部正常 |
| 克星题生成 | ✅ 5道Python陷阱题 |
