import os
from threading import Lock

# Reduce gRPC fork-related issues under dev hot-reload/fork scenarios.
os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "1")

from langchain_milvus import Milvus
from pymilvus import connections
from pymilvus.milvus_client import MilvusClient

from .config import settings
from .embed_core import get_embedding_model


class VectorStoreManager:
    def __init__(self):
        self._store: Milvus | None = None
        self._init_lock = Lock()

    @property
    def store(self) -> Milvus:
        """透明的懒加载：访问即初始化"""
        if self._store is None:
            self._init_client()
        return self._store

    def _init_client(self):
        """内部初始化逻辑"""
        with self._init_lock:
            if self._store is not None:
                return

            connection_args = {
                "uri": settings.MILVUS_URI,
                "db_name": settings.MILVUS_DB_NAME,
            }
            if settings.MILVUS_TOKEN:
                connection_args["token"] = settings.MILVUS_TOKEN

            client = MilvusClient(**connection_args)
            alias = client._using

            if not connections.has_connection(alias):
                connect_kwargs = {
                    "alias": alias,
                    "uri": settings.MILVUS_URI,
                    "db_name": settings.MILVUS_DB_NAME,
                }
                if settings.MILVUS_TOKEN:
                    connect_kwargs["token"] = settings.MILVUS_TOKEN
                connections.connect(**connect_kwargs)

            # 实例化真正的 Store
            self._store = Milvus(
                # embedding service is unified in app.core.embed_core
                embedding_function=get_embedding_model(),
                connection_args=connection_args,
                collection_name=settings.COLLECTION_NAME,
                auto_id=False,
                primary_field="pk",
                text_field="text",
                vector_field="vector",
            )


# 创建单例 - 现在的 import 成本几乎为 0
vector_manager = VectorStoreManager()
