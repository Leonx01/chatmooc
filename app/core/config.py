from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"

class Settings(BaseSettings):
    # Pydantic v2: use SettingsConfigDict (v1-style inner Config is ignored).
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # =========================
    # External API keys
    # =========================
    # Defaults keep static analyzers (e.g. PyCharm) from flagging Settings() as "missing args".
    # Runtime values should typically come from environment or `.env`.
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_API_KEY: str = ""
    DASHSCOPE_API_KEY: str = ""

    LANGSMITH_API_KEY: str = ""
    LANGSMITH_TRACING: bool = True
    LANGSMITH_PROJECT: str = "chatmooc"
    LANGCHAIN_TRACING_V2: bool = True

    # =========================
    # Application
    # =========================
    APP_NAME: str = "chatmooc_backend"
    APP_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    # MYSQL
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "chatmooc"
    MYSQL_DATABASE: str = "chatmooc"
    MYSQL_PORT: int = 3308

    # =========================
    # RabbitMQ
    # =========================
    RABBITMQ_URL: str = "amqp://guest:guest@localhost//"
    RESOURCE_PARSE_QUEUE: str = "resource_parse_queue"

    # =========================
    # Celery
    # =========================
    CELERY_BROKER_URL: str = ""  # 若为空，将 fallback 到 RABBITMQ_URL
    CELERY_RESULT_BACKEND: str = "rpc://"

    # =========================
    # Redis
    # =========================
    REDIS_URL: str = ""
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_KEY_PREFIX: str = "chatmooc"
    RATE_LIMIT_CAPACITY: int = 20  # 默认桶容量
    RATE_LIMIT_REFILL_RATE: float = 1.0  # 每秒补充令牌数量
    RATE_LIMIT_TTL_SECONDS: int = 0  # 0 表示不过期

    # =========================
    # Milvus
    # =========================
    MILVUS_URI: str = "http://127.0.0.1:19530"
    MILVUS_HOST: str = "127.0.0.1"
    MILVUS_PORT: int = 19530
    MILVUS_TOKEN: str = ""
    MILVUS_DB_NAME: str = "default"
    COLLECTION_NAME: str = "chatmooc_dev"
    EMBEDDING_MODEL: str = "text-embedding-v1"

    # =========================
    # Storage
    # =========================
    STORAGE_BACKEND: str = "local"  # local | oss
    LOCAL_STORAGE_DIR: str = "volumes/uploads"
    LOCAL_STORAGE_BASE_URL: str = "http://127.0.0.1:8000/files"
    LOCAL_PARSED_DIR: str = "volumes/parsed"
    OSS_ENDPOINT: str = ""
    OSS_BUCKET: str = ""
    OSS_ACCESS_KEY: str = ""
    OSS_SECRET_KEY: str = ""
    OSS_PUBLIC_BASE_URL: str = ""

settings = Settings()


def _normalize_url(raw: str) -> str:
    cleaned = (raw or "").strip()
    # Treat comment-only placeholders as empty so fallback logic works.
    return "" if cleaned.startswith("#") else cleaned


# Normalize broker URLs and apply fallback.
settings.RABBITMQ_URL = _normalize_url(settings.RABBITMQ_URL)
settings.CELERY_BROKER_URL = _normalize_url(settings.CELERY_BROKER_URL)
if not settings.RABBITMQ_URL:
    settings.RABBITMQ_URL = "amqp://guest:guest@localhost//"
if not settings.CELERY_BROKER_URL:
    settings.CELERY_BROKER_URL = settings.RABBITMQ_URL
