from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

# 1. 配置远程 SerpApi MCP 地址
# 注意：远程 MCP 通常走的是 SSE 协议，而不是本地的 stdio
SERPAPI_KEY = "你的_SERP_API_KEY"
mcp_url = f"https://mcp.serpapi.com/{SERPAPI_KEY}/mcp"

async def get_serp_tools():
    # 使用 SSE 客户端连接远程服务器
    async with MultiServerMCPClient(
        {"serpapi": {"url": mcp_url, "transport": "sse"}}
    ) as client:
        async with client.session("serpapi") as session:
            # 自动加载 SerpApi 提供的 search 等工具
            tools = await load_mcp_tools(session)
            return tools

# 之后将这些 tools 传入你的 LangGraph 节点即可