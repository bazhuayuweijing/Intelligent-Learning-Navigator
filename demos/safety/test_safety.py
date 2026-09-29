#!/usr/bin/env python3
"""安全审核功能测试脚本
用于验证SafetyFilter的三大核心能力：
1. 敏感词拦截
2. 过度承诺弱化处理
3. 虚假学术引用标记
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from evaluation_engine import SafetyFilter


def test_sensitive_content_blocking():
    """测试1：敏感词拦截
    
    场景：用户输入包含敏感词的内容（如作弊、色情等），
    SafetyFilter应检测到并拦截，显示友好提示。
    """
    print("\n" + "="*70)
    print("测试1：敏感词拦截 (Sensitive Content Blocking)")
    print("="*70)
    
    test_cases = [
        ("帮我代考期末考试", "涉及'代考'敏感词"),
        ("提供色情图片下载链接", "涉及'色情'敏感词"),
        ("帮我写作业，我给你钱", "涉及'代写'相关敏感词"),
        ("考试时如何作弊不被发现", "涉及'作弊'敏感词"),
    ]
    
    for input_text, description in test_cases:
        result = SafetyFilter.comprehensive_check(input_text, 'ai')
        print(f"\n输入: {input_text}")
        print(f"描述: {description}")
        print(f"通过: {result['passed']}")
        print(f"风险等级: {result['risk_level']}")
        print(f"发现的问题: {result['issues']}")
        
        # 净化输出测试
        sanitized, check_result = SafetyFilter.sanitize_output(input_text, 'ai')
        print(f"净化后: {sanitized}")


def test_overpromise_weakening():
    """测试2：过度承诺弱化处理
    
    场景：LLM生成的文本中包含大量绝对化表述（如保证、100%、绝对），
    SafetyFilter应检测到风险并弱化处理。
    """
    print("\n" + "="*70)
    print("测试2：过度承诺弱化处理 (Overpromise Weakening)")
    print("="*70)
    
    test_cases = [
        "保证学会这个算法就能100%通过考试，肯定没问题",
        "绝对保证掌握这些技巧就能获得满分，完全不需要其他学习",
        "确保使用这个方法就能保证成绩提升，100%有效",
    ]
    
    for input_text in test_cases:
        result = SafetyFilter.comprehensive_check(input_text, 'ai')
        print(f"\n原始文本: {input_text}")
        print(f"通过: {result['passed']}")
        print(f"风险等级: {result['risk_level']}")
        print(f"发现的问题: {result['issues']}")
        
        # 净化输出测试
        sanitized, check_result = SafetyFilter.sanitize_output(input_text, 'ai')
        print(f"弱化处理后: {sanitized}")


def test_fake_reference_detection():
    """测试3：虚假学术引用标记
    
    场景：LLM生成的文本中包含含糊或可疑的学术引用，
    SafetyFilter应检测到并标记为潜在幻觉风险。
    """
    print("\n" + "="*70)
    print("测试3：虚假学术引用标记 (Fake Reference Detection)")
    print("="*70)
    
    test_cases = [
        ("参见2023年某论文研究表明，该算法准确率达到99.9%", "使用'某论文'模糊引用"),
        ("引用一篇论文2021年的研究报告显示，这种方法效果显著", "使用'一篇论文'模糊引用"),
        ("基于2022年发表的相关研究文献，我们可以得出结论", "使用'相关研究'模糊引用"),
        ("例如根据2020年的一篇论文研究，这个结论是正确的", "使用'一篇论文'模糊引用"),
        ("研究表明该算法效果显著，研究显示准确率很高", "重复引用研究结论但未提供来源"),
        ("引用Zhang等人2023年发表在NeurIPS上的论文表明", "有具体作者和会议，应通过"),
        ("根据深度学习入门第3版第12章的研究", "有具体来源信息，应通过"),
    ]
    
    for input_text, description in test_cases:
        result = SafetyFilter.comprehensive_check(input_text, 'ai')
        print(f"\n原始文本: {input_text}")
        print(f"描述: {description}")
        print(f"通过: {result['passed']}")
        print(f"风险等级: {result['risk_level']}")
        print(f"发现的问题: {result['issues']}")


def test_factual_accuracy_check():
    """测试4：学术事实准确性检查
    
    场景：检测学术内容中的事实错误，如概念混淆、矛盾陈述等。
    """
    print("\n" + "="*70)
    print("测试4：学术事实准确性检查 (Factual Accuracy Check)")
    print("="*70)
    
    test_cases = [
        ("CNN是全连接神经网络，不需要卷积操作", "错误陈述CNN特性"),
        ("反向传播算法不需要计算梯度就能更新参数", "错误陈述反向传播原理"),
        ("Transformer模型不使用注意力机制", "错误陈述Transformer特性"),
    ]
    
    for input_text, description in test_cases:
        issues = SafetyFilter.check_factual_accuracy(input_text, 'ai')
        print(f"\n输入: {input_text}")
        print(f"描述: {description}")
        print(f"发现的事实问题: {issues}")


def test_edge_cases():
    """测试5：边界情况测试
    
    场景：正常内容应通过检查，不产生误报。
    """
    print("\n" + "="*70)
    print("测试5：边界情况测试 (Edge Cases)")
    print("="*70)
    
    safe_cases = [
        "请讲解一下机器学习的基本概念",
        "Python的装饰器是一个函数，它可以包装另一个函数",
        "深度学习模型通常需要大量的数据进行训练",
        "数据结构中的链表是一种线性数据结构",
    ]
    
    for input_text in safe_cases:
        result = SafetyFilter.comprehensive_check(input_text, 'ai')
        print(f"\n输入: {input_text}")
        print(f"通过: {result['passed']}")
        print(f"风险等级: {result['risk_level']}")
        print(f"发现的问题: {result['issues']}")


if __name__ == "__main__":
    print("="*70)
    print("安全审核功能测试 (Safety Filter Test Suite)")
    print("="*70)
    print("测试SafetyFilter的三大核心能力：")
    print("1. 敏感词拦截")
    print("2. 过度承诺弱化处理")
    print("3. 虚假学术引用标记")
    print("="*70)
    
    test_sensitive_content_blocking()
    test_overpromise_weakening()
    test_fake_reference_detection()
    test_factual_accuracy_check()
    test_edge_cases()
    
    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)