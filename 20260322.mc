# 2026-03-22 Debug 复盘（LangGraph + Tool + Milvus）

## 1. 背景与目标

今天主要目标是把 Tutor Agent 的长期记忆和检索链路跑通，并解决在 `langgraph dev` 下反复出现的 pending、超时和参数注入问题。

核心诉求：

- 长期记忆按 `unit_id` 隔离（而不是全局混用）。
- 模型在阶段完成/发现薄弱点时写入 memo。
- 每次会话时能检索长期记忆。
- `fetch_info` 工具在 Studio / API / dev 环境都稳定可用。

---

## 2. 关键问题与定位过程

### 2.1 语法错误导致图加载失败

现象：

- `tutor_agent.py` 导出段出现 `SyntaxError`，`langgraph dev` 无法加载 graph。

处理：

- 修复导出代码，恢复 `agent = get_agent(with_checkpointer=False)`（后续又优化为直接 compile 导出）。

---

### 2.2 thread_id / unit_id 语义混乱

现象：

- 一会按 `thread_id` 检索，一会按 `unit_id` 检索，配置和日志难排查。

处理：

- 最终业务记忆命名空间统一按 `user_id + unit_id`。
- 但 LangGraph checkpoint 仍需 `thread_id`，在 chat 路由中内部生成/传递。

---

### 2.3 自定义 tool_node 与 Injected 参数冲突

现象：

- `fetch_info_tool requires injected resource_ids and injected user_id`
- `memo_tool` 类似缺参问题。

原因：

- 自定义 `tool_node` 手工调用工具时，Injected 语义不稳定，维护成本高。

处理：

- 切换到官方 `ToolNode(TOOLS)`。
- 统一工具上下文读取方式，减少“半自动注入 + 手工补注入”的混合逻辑。

---

### 2.4 ToolRuntime 参数注入踩坑

现象：

- `TypeError: fetch_info_tool() missing 1 required positional argument: 'runtime'`

定位结论：

- 在当前版本组合下，`runtime` 注解写成 `Optional[ToolRuntime]` 会影响 injected 参数识别；
- 改为直接 `runtime: ToolRuntime` 后，工具 injected key 可被识别。

---

### 2.5 memory store 初始化时机问题

现象：

- `RuntimeError: Agent memory store is not initialized.`

原因：

- dev 直连运行时，FastAPI lifespan 不一定覆盖图节点执行路径。

处理：

- 在 `llm_call` 内做按需初始化兜底（仅在未初始化时 init）。

---

### 2.6 Redis memory store API 形态差异

现象：

- `'_AsyncGeneratorContextManager' object has no attribute 'asetup'`

原因：

- 当前 `AsyncRedisStore.from_conn_string` 返回 async context manager，而非直接实例。

处理：

- `memory_store.py` 兼容两种初始化形态（上下文管理器/直接实例），并修复关闭逻辑。

---

### 2.7 fetch_info 卡死 / pending / 超时

现象：

- `Thread pending`
- `Search timeout ...`
- `search_start` 后长时间无 `search_done`

已确认事实：

- 注入是成功的（日志可见 `context=GraphConfig(...)` 和正确 keys）。
- Milvus 本身可返回（单独探针查询可稳定返回结果）。
- 首次链路慢主要在初始化与 embedding，且 dev 热重载会放大“卡死”体感。

处理：

- 增加分阶段日志：runtime、search_start、embed_done、search_done、total_done。
- 分段超时与错误码：`embed_timeout` / `search_timeout` / `embed_failed` / `search_failed`。
- 清洗 `resource_ids` 空值。
- 将阻塞型调用放入线程池：
  - embedding：`asyncio.to_thread(...embed_query...)`
  - search：`asyncio.to_thread(...similarity_search_with_score_by_vector...)`
- 增加 gRPC fork 兼容环境变量：`GRPC_ENABLE_FORK_SUPPORT=1`（导入 pymilvus 前设置）。

---

### 2.8 Embedding 服务切换与依赖问题

过程：

- 先切到 Ollama，后按需求切回 DashScope。

最终：

- `embed_core` 工程化为懒加载 + 线程安全统一入口。
- `milvus_core` 统一从 `embed_core` 获取 embedding 实例。
- 配置改为从 `settings` 读取 DashScope key（去除硬编码）。

问题：

- `ModuleNotFoundError: dashscope`（Celery worker 缺依赖）。

结论：

- 安装依赖后不会自动重跑旧失败任务；需重启 worker 并重新触发任务。

---

### 2.9 Celery 至少一次消费保障

已加配置：

- `task_acks_late=True`
- `task_reject_on_worker_lost=True`
- `task_acks_on_failure_or_timeout=False`

并为 `parse_resource` 增加有限自动重试（指数退避 + 最大重试次数）。

---

## 3. 本次 Debug 的有效经验

1. 先分清“注入失败”还是“执行阻塞”：日志必须分层打印。  
2. 在 `langgraph dev` 下，先关热重载（`--no-reload`）再定位超时。  
3. 对向量检索要做分阶段计时（embed/search），否则会误判 Milvus。  
4. 至少一次语义不是“只靠 broker”，任务幂等和重试策略同样关键。  
5. 工程配置必须去硬编码（尤其 API Key），统一走 settings/.env。

---

## 4. 后续建议（可选）

- 在 `fetch_info` 增加短 TTL 缓存（同 `thread_id + query + resource_ids`）减少重复检索。
- 提示词约束单轮最多一次 `fetch_info`，避免模型重复调用。
- 增加启动预热：embedding + 轻量检索，降低首轮冷启动抖动。
- 提供 `/admin/queue-metrics` 轻量接口，统一观察队列与 worker 状态。

