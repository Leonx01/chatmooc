from pymilvus import MilvusClient, DataType

client = MilvusClient(uri="http://localhost:19530")

collection_name = "chatmooc_dev"

# ⚠️ 生产环境不要随便 drop
if client.has_collection(collection_name):
    client.drop_collection(collection_name)

# ========= Schema =========
schema = client.create_schema(
    auto_id=False,  # ✅ 改成手动主键
    enable_dynamic_field=False  # ❌ 关闭动态字段（更可控 & 更高性能）
)

# 主键（建议用 hash）
schema.add_field(
    field_name="pk",
    datatype=DataType.VARCHAR,
    is_primary=True,
    max_length=64
)

# 用户隔离
schema.add_field(
    field_name="user_id",
    datatype=DataType.VARCHAR,
    max_length=64
)

# 资源隔离
schema.add_field(
    field_name="resource_id",
    datatype=DataType.VARCHAR,
    max_length=64
)

# chunk 文本
schema.add_field(
    field_name="text",
    datatype=DataType.VARCHAR,
    max_length=2048
)

# 父文本（可选）
schema.add_field(
    field_name="parent_text",
    datatype=DataType.VARCHAR,
    max_length=4096
)

# 时间戳（非常重要）
schema.add_field(
    field_name="create_time",
    datatype=DataType.INT64
)

# 向量
schema.add_field(
    field_name="vector",
    datatype=DataType.FLOAT_VECTOR,
    dim=1024
)

# ========= Index =========
index_params = client.prepare_index_params()

# 向量索引（优化参数）
index_params.add_index(
    field_name="vector",
    index_type="HNSW",
    metric_type="COSINE",
    params={
        "M": 12,              # ✅ 降低内存
        "efConstruction": 200 # ✅ 提高构建速度
    }
)

# 标量索引
index_params.add_index(
    field_name="resource_id",
    index_type="STL_SORT"
)

index_params.add_index(
    field_name="user_id",
    index_type="STL_SORT"
)

# 时间索引（可选）
index_params.add_index(
    field_name="create_time",
    index_type="STL_SORT"
)

# ========= Create =========
client.create_collection(
    collection_name=collection_name,
    schema=schema,
    index_params=index_params
)

print("✅ Collection 创建完成（优化版）")