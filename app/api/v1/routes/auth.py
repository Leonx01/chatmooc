from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models import Users
from app.schema.users import LoginResponse, UserLogin
from app.service.user_service import UserService, get_user_service
from app.utils.token_gen import JWTTool

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: UserLogin,
    user_service: UserService = Depends(get_user_service),
) -> LoginResponse:
    user = await user_service.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = JWTTool.create_access_token(data={"sub": user.uid, "uname": user.uname})
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        uid=user.uid,
        username=user.uname,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    user_service: UserService = Depends(get_user_service),
) -> Users:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
        )

    payload = JWTTool.verify_token(str(credentials.credentials))
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌",
        )

    user = await user_service.get_by_uid(str(payload["sub"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user
