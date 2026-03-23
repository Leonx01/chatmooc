import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt


class JWTTool:
    """
    JWT 工具类：用于生成和校验加密令牌
    """

    # 建议生产环境从环境变量读取，如 os.getenv("JWT_SECRET")
    SECRET_KEY = "10f5a41be8bfc3b73cb9d5e05caa90e07aea782ac3bd52d2da0b7504f48f4d58"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 默认有效期 24 小时

    @classmethod
    def create_access_token(
        cls, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        生成 JWT Token
        :param data: 需要加密进负载（Payload）的数据
        :param expires_delta: 可选的过期时间偏移量
        """
        to_encode = data.copy()

        # 设置过期时间
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        # 标准字段：exp (过期时间), iat (发行时间), jti (唯一标识)
        to_encode.update(
            {
                "exp": expire,
                "iat": datetime.now(timezone.utc),
                "jti": str(uuid.uuid4()),  # 每次生成 Token 都有唯一的 ID
            }
        )

        encoded_jwt = jwt.encode(to_encode, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
        return encoded_jwt

    @classmethod
    def verify_token(cls, token: str) -> Optional[Dict[str, Any]]:
        """
        校验并解析 Token
        :param token: 待校验的 Token 字符串
        :return: 解析后的 Payload，如果无效则返回 None
        """
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            print("Token 已过期")
            return None
        except jwt.InvalidTokenError:
            print("Token 无效")
            return None
        except Exception as e:
            print(f"校验异常: {e}")
            return None


# ===== 使用示例 =====
if __name__ == "__main__":
    # 1. 模拟登录，存入用户 ID 和生成的 UUID 会话
    user_session = {"sub": "user_12345", "sid": str(uuid.uuid4()), "role": "admin"}

    token = JWTTool.create_access_token(data=user_session)
    print(f"Generated JWT: {token}")

    # 2. 模拟校验请求头中的 Token
    decoded = JWTTool.verify_token(token)
    if decoded:
        print(f"Decoded Payload: {decoded}")
        print(f"Session ID (sid) from Token: {decoded.get('sid')}")
