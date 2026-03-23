from functools import partial

from fastapi import APIRouter, Depends

from app.api.deps import rate_limiter

router = APIRouter(prefix="/test", tags=["test"])
# 场景：普通接口，每秒 2 个，桶容量 5
standard_limit = partial(rate_limiter, capacity=5, rate=2.0, prefix="std")

# 场景：高频搜索接口，每秒 10 个，桶容量 20
search_limit = partial(rate_limiter, capacity=20, rate=10.0, prefix="search")


@router.get("/items")
async def get_items(auth=Depends(standard_limit)):
    return {"data": "items"}


@router.get("/search")
async def search(q: str, auth=Depends(search_limit)):
    return {"results": f"Result for {q}"}
