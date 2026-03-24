# ChatMooc - AI-Powered Tutoring Platform

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1+-blue.svg)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

ChatMooc 是一个 AI 驱动的个性化学习平台，使用 LangGraph 代理技术提供智能辅导体验。用户可以上传学习资源（PDF、文档、视频等），AI 导师会自动生成学习路径、闪卡和练习题。

## ✨ 主要特性

- 🤖 **智能导师代理** - 基于 LangGraph 的高级 AI 代理系统
- 📚 **资源管理** - 支持多种文档格式（PDF、Word、PowerPoint）
- 🎯 **个性化学习路径** - 根据用户进度动态规划学习计划
- 💾 **向量数据库** - 使用 Milvus 进行高效的语义搜索
- ⚡ **异步处理** - 通过 Celery 实现后台任务队列
- 🔐 **JWT 认证** - 完整的用户身份验证和授权
- 🌊 **实时流式响应** - SSE（Server-Sent Events）支持实时流式输出
- 📊 **多 LLM 支持** - 支持 OpenAI、DeepSeek、Ollama 等

## 📋 前置要求

- Python 3.12+
- Docker 和 Docker Compose
- MySQL 8.0+
- Redis 6.0+
- Milvus 2.0+

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Leonx01/chatmooc.git
cd chatmooc
```

### 2. 启动基础设施服务

```bash
docker compose up -d
```

这将启动以下服务：
- MySQL（数据库）
- Redis（缓存和会话存储）
- Milvus（向量数据库）
- RabbitMQ（消息队列）
- Ollama（本地 LLM）

### 3. 安装依赖

```bash
uv pip install -e .
# 或使用 pip
pip install -e .
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，设置必要的配置
```

**关键环境变量：**
- `LLM_NAME`: 默认 LLM（deepseek, gpt-4o-mini, claude-3-5-sonnet, ollama）
- `DATABASE_URL`: MySQL 连接字符串
- `REDIS_URL`: Redis 连接字符串
- `MILVUS_HOST`: Milvus 服务地址

### 5. 启动应用

```bash
# 启动 FastAPI 服务器
uvicorn app.main:app --reload --port 8000

# 在另一个终端启动 Celery 工作进程
celery -A app.core.celery_core worker --loglevel=info
```

访问 API 文档：http://localhost:8000/docs

## 📁 项目结构

```
chatmooc/
├── app/
│   ├── agents/                 # AI 代理模块
│   │   ├── tutor_agent.py     # 核心导师代理
│   │   ├── planner_agent.py   # 学习路径规划器
│   │   ├── tools/             # 代理工具集
│   │   └── prompts/           # 系统提示词
│   ├── api/
│   │   └── v1/
│   │       └── routes/        # API 路由
│   │           ├── auth.py    # 认证相关
│   │           ├── resources.py # 资源管理
│   │           ├── chat.py    # 聊天 SSE 流
│   │           └── test.py    # 测试端点
│   ├── core/                  # 核心服务
│   │   ├── config.py          # 配置管理
│   │   ├── mysql_core.py      # 数据库连接
│   │   ├── redis_core.py      # Redis 连接
│   │   ├── milvus_core.py     # 向量数据库
│   │   ├── celery_core.py     # Celery 配置
│   │   └── storage.py         # 文件存储
│   ├── models/                # 数据模型
│   ├── schemas/               # Pydantic 模式
│   └── main.py               # 应用入口
├── db/
│   └── schema.md             # 数据库架构文档
├── tests/                    # 测试套件
│   ├── conftest.py          # 测试配置和 fixtures
│   ├── test_api/            # API 测试
│   └── test_services/       # 服务测试
├── docker-compose.yml       # Docker 组合配置
├── pyproject.toml          # 项目依赖配置
├── pytest.ini              # pytest 配置
└── CLAUDE.md              # Claude 开发指南
```

## 🔌 核心组件

### 代理系统
- **tutor_agent.py**: LangGraph StateGraph 工作流（llm_call → tool_node → 循环）
- **planner_agent.py**: 学习路径规划
- **tools/**: 闪卡、练习、备忘录、信息获取工具
- **prompts/**: 代理系统提示词

### API 路由
| 端点 | 方法 | 功能 |
|------|------|------|
| `/auth/login` | POST | 用户登录 |
| `/auth/register` | POST | 用户注册 |
| `/resources/upload` | POST | 上传学习资源 |
| `/chat/stream` | POST | SSE 流式聊天 |

### 核心服务
- **config.py**: Pydantic Settings 配置管理
- **mysql_core.py**: SQLAlchemy 数据库连接
- **redis_core.py**: Redis 缓存和会话
- **milvus_core.py**: 向量数据库存储和检索
- **celery_core.py**: 异步任务队列
- **storage.py**: 本地/OSS 文件存储

## 🗄️ 数据库架构

主要数据表：
- **Users**: 用户账户信息
- **Resources**: 上传的学习资源
- **Sessions**: 用户学习会话
- **Units**: 学习单元
- **FlashCards**: 闪卡
- **Exercises**: 练习题
- **MilvusVectors**: 向量嵌入

详见 `db/schema.md`

## ✅ 测试

### 运行所有测试

```bash
pytest
```

### 运行单元测试（快速，无依赖）

```bash
pytest tests/ -m unit
```

### 运行集成测试（需要运行的服务）

```bash
pytest tests/ -m integration
```

### 运行特定测试文件

```bash
pytest tests/test_services/test_config.py -v
```

### 测试结构
- `tests/conftest.py`: 共享 fixtures 和测试配置
- `tests/test_api/`: API 端点测试
- `tests/test_services/`: 服务和模型测试

### 测试标记
- `@pytest.mark.unit`: 快速测试，无外部依赖
- `@pytest.mark.integration`: 需要运行服务的测试

## ⚙️ 配置管理

环境变量通过 `.env` 文件定义，由 `app/core/config.py` 加载。

**关键设置：**
- `LLM_NAME`: 默认 LLM 模型
- `DATABASE_URL`: MySQL 连接字符串
- `REDIS_URL`: Redis 端点
- `MILVUS_HOST`: Milvus 服务地址
- `STORAGE_BACKEND`: 存储后端（local/oss）

## 🤖 代理配置

导师代理需要以下可配置参数：
- `user_id`: 用户标识符
- `unit_id`: 学习单元标识符
- `resource_ids`: 参考资源 ID 列表

这些参数通过 LangGraph 的 `configurable` 字段在聊天 API 中传递。

## 🔒 认证和安全

- JWT（JSON Web Token）认证
- 密码加密存储
- 会话管理由 Redis 支持
- API 速率限制

## 📚 依赖项

主要依赖：
- **FastAPI**: 现代 Web 框架
- **LangChain & LangGraph**: AI 代理框架
- **SQLAlchemy**: ORM 数据库
- **Celery**: 分布式任务队列
- **Milvus**: 向量数据库
- **Redis**: 缓存和会话存储
- **Pydantic**: 数据验证

完整依赖列表见 `pyproject.toml`

## 🚢 部署

### Docker 部署

```bash
docker build -t chatmooc:latest .
docker run -p 8000:8000 chatmooc:latest
```

### 环境变量

部署前确保设置所有必需的环境变量：
- LLM API 密钥
- 数据库凭证
- Redis 和 Milvus 连接信息

## 📝 开发指南

详见 `CLAUDE.md` 获得更多开发相关的指导和 best practices。

### 常用命令

```bash
# 格式化代码（Black + isort）
black .
isort .

# 运行 LangGraph 开发服务器
langgraph dev

# 生成数据库代码
sqlacodegen mysql://user:password@localhost/chatmooc
```

## 🐛 常见问题

### 服务连接失败
确保 Docker 服务已启动：
```bash
docker compose ps
```

### 导入错误
确保已正确安装所有依赖：
```bash
pip install -e .
```

### 数据库迁移
如需更新数据库架构，参考 `db/schema.md`

## 📄 许可证

[待定 - 请选择合适的许可证]

## 👤 作者

- **Leonx01** - 初始开发者

## 🤝 贡献

欢迎提交 Pull Request 和 Issue！

## 📞 支持

遇到问题？请：
1. 查看 `CLAUDE.md` 中的故障排除部分
2. 提交 GitHub Issue
3. 联系开发者

## 📚 更多资源

- [LangChain 文档](https://python.langchain.com/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Milvus 文档](https://milvus.io/)
