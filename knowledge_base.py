"""轻量级本地知识库 — TF-IDF检索

为LLM生成提供知识库上下文支持，确保生成内容的知识准确性。
不做完整RAG，不依赖外部服务，纯Python标准库实现。

用法：
    from knowledge_base import kb
    context = kb.get_context(query="二分查找", subject="computer_science")
    # 将context拼入LLM的system_prompt即可
"""
import os
import re
import glob
from collections import Counter
from math import log


class LocalKnowledgeBase:
    """基于TF-IDF的本地知识库检索

    从 data/knowledge_base/<subject>/*.md 加载知识文档，
    对查询做TF-IDF加权检索，返回最相关文档作为LLM上下文。
    """

    def __init__(self, kb_dir=None):
        if kb_dir is None:
            base = os.path.dirname(os.path.abspath(__file__))
            self.kb_dir = os.path.join(base, 'data', 'knowledge_base')
        else:
            self.kb_dir = kb_dir
        self.docs = []          # [(subject, title, content)]
        self.doc_vectors = []   # [{term: tfidf}]
        self.idf = {}           # {term: idf}
        self._loaded = False

    def load(self):
        """扫描knowledge_base目录，加载所有.md文件"""
        self.docs = []
        if not os.path.isdir(self.kb_dir):
            print(f"[KnowledgeBase] 知识库目录不存在: {self.kb_dir}")
            self._loaded = True
            return
        for subject in sorted(os.listdir(self.kb_dir)):
            subject_dir = os.path.join(self.kb_dir, subject)
            if not os.path.isdir(subject_dir):
                continue
            for fname in sorted(os.listdir(subject_dir)):
                if not fname.endswith('.md'):
                    continue
                fpath = os.path.join(subject_dir, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                title = fname.replace('.md', '')
                self.docs.append((subject, title, content))
        print(f"[KnowledgeBase] 已加载 {len(self.docs)} 篇知识文档 "
              f"({len(set(s for s,_,_ in self.docs))}个学科)")
        self._build_index()
        self._loaded = True

    @staticmethod
    def _tokenize(text):
        """简单分词：英文单词 + 中文二元组"""
        words = re.findall(r'[a-zA-Z_]+', text.lower())
        chinese_chunks = re.findall(r'[\u4e00-\u9fff]+', text)
        for chunk in chinese_chunks:
            if len(chunk) <= 2:
                words.append(chunk)
            else:
                for i in range(len(chunk) - 1):
                    words.append(chunk[i:i+2])
        return words

    def _build_index(self):
        """构建TF-IDF索引"""
        n = len(self.docs)
        if n == 0:
            self.idf = {}
            self.doc_vectors = []
            return
        df = Counter()
        doc_term_lists = []
        for _, _, content in self.docs:
            terms = self._tokenize(content)
            unique = set(terms)
            doc_term_lists.append(terms)
            for t in unique:
                df[t] += 1
        self.idf = {t: log(n / (1 + c)) + 1 for t, c in df.items()}
        self.doc_vectors = []
        for terms in doc_term_lists:
            tf = Counter(terms)
            max_tf = max(tf.values()) if tf else 1
            vector = {}
            for t, c in tf.items():
                vector[t] = (c / max_tf) * self.idf.get(t, 1)
            self.doc_vectors.append(vector)

    def search(self, query, subject=None, top_k=3):
        """检索相关文档

        Args:
            query: 查询文本
            subject: 限定学科，None时不限定
            top_k: 返回最多条数

        Returns:
            list of dict: [{"subject": str, "title": str, "content": str,
                           "relevance": float, "excerpt": str}]
        """
        if not self._loaded:
            self.load()
        if not self.docs or not query.strip():
            return []

        query_terms = self._tokenize(query)
        q_tf = Counter(query_terms)
        q_max = max(q_tf.values()) if q_tf else 1

        scored = []
        for idx, ((doc_subject, doc_title, doc_content), vector) in enumerate(
                zip(self.docs, self.doc_vectors)):
            if subject and doc_subject != subject:
                continue
            score = 0.0
            for t, c in q_tf.items():
                if t in vector:
                    score += (c / q_max) * vector[t]
            if score > 0:
                excerpt = doc_content[:200].replace('\n', ' ')
                scored.append((score, idx, doc_subject, doc_title, doc_content, excerpt))

        scored.sort(reverse=True)
        results = []
        for score, idx, s, t, content, excerpt in scored[:top_k]:
            results.append({
                'subject': s,
                'title': t,
                'content': content,
                'relevance': round(score, 3),
                'excerpt': excerpt,
            })
        return results

    def get_context(self, query, subject=None, top_k=2):
        """生成给LLM的上下文提示字符串

        检索到的文档格式化后作为system prompt的补充。
        无命中时返回空字符串，不干扰正常LLM生成。
        """
        results = self.search(query, subject, top_k)
        if not results:
            return ""
        parts = ["【以下知识库内容可参考，请在生成时以这些信息为基础：】"]
        for r in results:
            parts.append(f"\n--- 《{r['title']}》({r['subject']}) ---")
            parts.append(r['content'][:600])
        return "\n".join(parts)

    def get_subjects(self):
        """返回知识库中已有的学科列表"""
        if not self._loaded:
            self.load()
        return sorted(set(s for s, _, _ in self.docs))


# 全局实例：项目各处导入后直接用 kb.get_context(...)
kb = LocalKnowledgeBase()


# ===== 自测：python3 knowledge_base.py 可运行 =====
if __name__ == '__main__':
    kb.load()
    print(f"学科覆盖: {kb.get_subjects()}")
    for test_q in ["二分查找", "牛顿定律", "机器学习", "语法时态"]:
        ctx = kb.get_context(test_q, top_k=1)
        if ctx:
            print(f"\n查询「{test_q}」→ 命中")
        else:
            print(f"\n查询「{test_q}」→ 无命中")
