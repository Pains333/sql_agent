import math
import re
from typing import List, Dict, Tuple
from collections import Counter

class TableRetriever:
    """
    轻量级 TF-IDF 表结构检索器
    零依赖 (仅使用标准库)，用于在数据库表数量过多时，基于用户输入检索最相关的表结构
    """
    def __init__(self, top_k: int = 15):
        self.top_k = top_k
        self.documents: List[Dict] = []
        self.idf: Dict[str, float] = {}
        self.doc_count = 0

    def _tokenize(self, text: str) -> List[str]:
        # 简单分词：转小写，提取字母数字汉字组合
        text = str(text).lower()
        tokens = re.findall(r'[\w\u4e00-\u9fa5]+', text)
        return tokens

    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        tf = {}
        if not tokens:
            return tf
        counter = Counter(tokens)
        max_count = max(counter.values())
        for token, count in counter.items():
            tf[token] = count / max_count
        return tf

    def build_index(self, tables_info: List[Dict]):
        """
        构建 TF-IDF 索引
        tables_info 格式: [{"db": "db1", "table": "users", "schema": "id INT, name VARCHAR...", "desc": "用户表"}]
        """
        self.documents = []
        self.idf = {}
        self.doc_count = len(tables_info)

        # 临时存储每个词出现在多少个文档中
        df = Counter()

        for info in tables_info:
            # 将表名、列名、注释等拼接成文本
            text = f"{info['db']} {info['table']} {info.get('schema', '')} {info.get('desc', '')}"
            tokens = self._tokenize(text)
            
            # 为了提高表名本身的权重，把表名额外加入 tokens 中
            table_tokens = self._tokenize(info['table'])
            tokens.extend(table_tokens * 3) # 表名权重 x3

            tf = self._compute_tf(tokens)
            
            self.documents.append({
                "info": info,
                "tf": tf,
                "tokens": set(tokens)
            })

            for token in set(tokens):
                df[token] += 1

        # 计算 IDF
        for token, count in df.items():
            # 采用平滑的 IDF 计算公式
            self.idf[token] = math.log((self.doc_count + 1) / (count + 1)) + 1

    def retrieve(self, query: str) -> List[Dict]:
        """
        根据用户查询检索最相关的表
        """
        if self.doc_count == 0:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return [doc["info"] for doc in self.documents[:self.top_k]]

        query_tf = self._compute_tf(query_tokens)
        
        scores = []
        for doc in self.documents:
            score = 0.0
            for token in query_tokens:
                if token in doc["tf"] and token in self.idf:
                    # 计算 tf-idf 乘积作为该词的得分
                    score += query_tf[token] * doc["tf"][token] * self.idf[token]
            scores.append((score, doc["info"]))

        # 按得分降序排序
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # 返回 top_k
        results = [item[1] for item in scores[:self.top_k]]
        return results
