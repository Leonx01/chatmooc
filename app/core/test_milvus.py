import pytest
import asyncio
from pprint import pprint


# 确保导入了你的 hybrid_manager 实例
from app.core.milvus_core_v2 import hybrid_manager

@pytest.mark.asyncio  # <--- 关键：告诉 pytest 这是一个异步测试
async def test_hybrid_workflow():
    print("\n=== 开始 Milvus 混合检索全流程测试 ===")

    # 1. 配置参数
    user_id = "test_user_001"
    resource_id = "res_999"

    test_texts = [
        "人工智能是大数据的核心应用场景。",
        "深度学习通过多层神经网络提取特征。",
        "向量数据库是 RAG 架构中的重要组件。"
    ]
    parent_texts = ["AI概论", "深度学习基础", "RAG架构指南"]

    # 2. 清理并准备环境 (可选)
    # 如果你想每次测试都从头开始，取消下面注释
    # try:
    #     hybrid_manager.client.drop_collection(hybrid_manager.collection_name)
    #     hybrid_manager.create_hybrid_collection()
    # except:
    #     pass

    # 3. 执行写入
    print("\n[步骤 1] 正在插入数据...")
    upsert_res = await hybrid_manager.upsert_docs(
        texts=test_texts,
        parent_texts=parent_texts,
        user_id=user_id,
        resource_id=resource_id
    )
    print(f"插入完成，影响行数: {upsert_res.get('insert_count')}")

    # 4. 强制等待索引同步
    # Milvus 写入后到可搜索有一定延迟，测试环境建议稍微等一下
    await asyncio.sleep(1)

    # 5. 执行混合检索
    print("\n[步骤 2] 执行混合检索测试...")
    query = "什么是 RAG？"
    search_results = await hybrid_manager.hybrid_search(
        query=query,
        user_id=user_id,
        resource_ids=[resource_id],
        top_k=2
    )

    # 6. 断言验证
    print("\n[步骤 3] 验证结果:")
    pprint(search_results)

    assert len(search_results) > 0, "检索结果不应为空"
    assert "RAG" in search_results[0]["content"] or "向量数据库" in search_results[0]["content"]
    assert search_results[0]["resource_id"] == resource_id

    print("\n✅ 测试圆满通过！")


# 如果你想直接通过 python 运行而不是 pytest
if __name__ == "__main__":
    asyncio.run(test_hybrid_workflow())