from typing import AsyncGenerator, Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mysql_core import db_manager
from app.models import Users


class UserService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_uname(self, uname: str) -> Optional[Users]:
        result = await self._session.execute(
            select(Users).where(Users.uname == uname)
        )
        return result.scalar_one_or_none()

    async def get_by_uid(self, uid: str) -> Optional[Users]:
        result = await self._session.execute(
            select(Users).where(Users.uid == uid)
        )
        return result.scalar_one_or_none()

    async def authenticate(self, username: str, password: str) -> Optional[Users]:
        user = await self.get_by_uname(username)
        if not user or user.password != password:
            return None
        return user


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.get_session() as session:
        yield session


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)
