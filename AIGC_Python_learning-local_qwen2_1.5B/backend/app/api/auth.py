from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.core.database import get_db
from app.models.user import User


router = APIRouter()


def registration_password_error(password: str, username: str, phone: str) -> str | None:
    if not 12 <= len(password) <= 128 or not password.strip():
        return '新密码需为 12–128 个字符，建议使用密码管理器生成的独立密码'
    normalized = password.casefold()
    common_passwords = {
        '123456789012', '1234567890123456', 'password1234', 'password123!',
        'password123456', 'qwerty123456789', 'qwertyuiop123',
    }
    if (normalized in common_passwords or len(set(password)) == 1 or
            normalized == username.casefold() or password == phone):
        return '请勿使用常见密码、重复字符、用户名或手机号作为密码'
    return None


class UserCreate(BaseModel):
    username: str
    password: str
    phone: str


class UserLogin(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    code: int = 200
    msg: str = "操作成功"
    data: dict


@router.post("/auth/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    password_error = registration_password_error(user.password, user.username, user.phone)
    if password_error:
        # Do not echo the submitted password in a validation response.
        return AuthResponse(code=400, msg=password_error, data={})
    if db.query(User).filter(User.username == user.username).first():
        return AuthResponse(code=400, msg="用户名已存在", data={})
    if db.query(User).filter(User.phone == user.phone).first():
        return AuthResponse(code=400, msg="手机号已被注册", data={})

    new_user = User(
        username=user.username,
        password=get_password_hash(user.password),
        phone=user.phone,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return AuthResponse(
        code=201,
        msg="注册成功",
        data={"id": new_user.id, "username": new_user.username, "phone": new_user.phone},
    )


@router.post("/auth/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if db_user.status == "disabled":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已被禁用")
    token_data = {"sub": db_user.username}
    return AuthResponse(
        code=200,
        msg="登录成功",
        data={
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
            "token_type": "bearer",
        },
    )


@router.post("/auth/reset-password-request")
async def reset_password_request():
    raise HTTPException(status_code=410, detail="演示版暂未提供短信验证，密码重置已停用")


@router.post("/auth/reset-password")
async def reset_password():
    raise HTTPException(status_code=410, detail="演示版暂未提供短信验证，密码重置已停用")


@router.get("/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return AuthResponse(
        code=200,
        msg="获取成功",
        data={
            "id": current_user.id,
            "username": current_user.username,
            "phone": current_user.phone,
        },
    )
