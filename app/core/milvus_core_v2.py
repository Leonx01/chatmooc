import asyncio
import os
import time
import uuid
from threading import Lock
from typing import List, Dict

# 解决跨进程/热重载下的 gRPC 锁死问题
os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "1")

from pymilvus import (
    MilvusClient,
    AnnSearchRequest,
    RRFRanker
)
from pymilvus.model.hybrid import BGEM3EmbeddingFunction


class HybridVectorManager:
    def __init__(self, uri: str, token: str = "", db_name: str = "default"):
        self.uri = uri
        self.token = token
        self.db_name = db_name

        self._client: MilvusClient | None = None
        self._model: BGEM3EmbeddingFunction | None = None
        self._init_lock = Lock()

        # 配置信息：与 chatmooc_dev 截图保持一致
        self.collection_name = "chatmooc_dev"
        self.dim = 1024

    @property
    def client(self) -> MilvusClient:
        if self._client is None:
            self._init_resources()
        return self._client

    @property
    def model(self) -> BGEM3EmbeddingFunction:
        if self._model is None:
            self._init_resources()
        return self._model

    def _init_resources(self):
        """懒加载初始化"""
        with self._init_lock:
            if self._client is not None:
                return
            # 如果你有 GPU，建议设置 device="cuda"
            self._model = BGEM3EmbeddingFunction(use_fp16=True, device="cuda")
            self._client = MilvusClient(uri=self.uri, token=self.token, db_name=self.db_name)

    async def upsert_docs(self, texts: List[str], parent_texts: List[str], user_id: str, resource_id: str):
        """写入数据：同步生成双路向量"""
        output = await asyncio.to_thread(self.model, texts)

        data = []
        for i, text in enumerate(texts):
            data.append({
                "pk": str(uuid.uuid4()),
                "user_id": user_id,
                "resource_id": resource_id,
                "text": text,
                "parent_text": parent_texts[i] if i < len(parent_texts) else "",
                "create_time": int(time.time()),
                "vector": output["dense"][i],
                "sparse_vector": output["sparse"][i]
            })

        return await asyncio.to_thread(self.client.insert, self.collection_name, data)

    async def hybrid_search(
            self,
            query: str,
            user_id: str,
            resource_ids: List[str],
            top_k: int = 5
    ) -> List[Dict]:
        """执行混合检索"""
        output = await asyncio.to_thread(self.model, [query])
        query_dense = output["dense"][0]
        query_sparse = output["sparse"][0]

        # 构造过滤表达式
        safe_ids = [f'"{str(rid)}"' for rid in resource_ids]
        filter_expr = f'user_id == "{user_id}" and resource_id in [{", ".join(safe_ids)}]'

        # 修正 1：过滤条件 (expr) 必须写在各自的 AnnSearchRequest 里
        # 修正 2：HNSW 对应的搜索参数是 ef (代替无效的 nprobe)
        req_dense = AnnSearchRequest(
            data=[query_dense],
            anns_field="vector",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=top_k * 2,
            expr=filter_expr  # <--- 写在这里
        )

        # 修正 3：稀疏索引搜索时丢弃低权重词的参数是 drop_ratio_search
        req_sparse = AnnSearchRequest(
            data=[query_sparse],
            anns_field="sparse_vector",
            param={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
            limit=top_k * 2,
            expr=filter_expr  # <--- 写在这里
        )

        # 修正 4：删除了 client.hybrid_search 中的 filter 参数
        results = await asyncio.to_thread(
            self.client.hybrid_search,
            collection_name=self.collection_name,
            reqs=[req_dense, req_sparse],
            ranker=RRFRanker(),
            limit=top_k,
            output_fields=["text", "parent_text", "resource_id"]
        )

        return self._parse_results(results)

    @staticmethod
    def _parse_results(raw_results):
        formatted = []
        if not raw_results or len(raw_results) == 0: return formatted
        for hit in raw_results[0]:
            entity = hit.get("entity")
            formatted.append({
                "content": entity.get("text"),
                "parent_context": entity.get("parent_text"),
                "score": round(hit.get("distance"), 4),
                "resource_id": entity.get("resource_id"),
                "pk": hit.get("id")
            })
        return formatted


# 实例化
hybrid_manager = HybridVectorManager(uri="http://localhost:19530")
