from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from datetime import timedelta
from app.core.database import get_db
from app.core.auth import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.models.user import User
from pydantic import BaseModel

router = APIRouter()

# 请求和响应模型
class UserCreate(BaseModel):
    username: str
    password: str
    phone: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    phone: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class PasswordResetRequest(BaseModel):
    phone: str

class PasswordReset(BaseModel):
    phone: str
    new_password: str

class AuthResponse(BaseModel):
    code: int = 200
    msg: str = "操作成功"
    data: dict

# 注册接口
@router.post("/auth/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        return AuthResponse(
            code=400,
            msg="用户名已存在",
            data={}
        )
    
    # 检查手机号是否已存在
    existing_phone = db.query(User).filter(User.phone == user.phone).first()
    if existing_phone:
        return AuthResponse(
            code=400,
            msg="手机号已被注册",
            data={}
        )
    
    # 密码哈希
    hashed_password = get_password_hash(user.password)
    
    # 创建用户
    new_user = User(
        username=user.username,
        password=hashed_password,
        phone=user.phone
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return AuthResponse(
        code=201,
        msg="注册成功",
        data={
            "id": new_user.id,
            "username": new_user.username,
            "phone": new_user.phone
        }
    )

# 登录接口
@router.post("/auth/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    # 查找用户
    db_user = db.query(User).filter(User.username == user.username).first()
    
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    if db_user.status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    # 创建访问令牌和刷新令牌
    access_token = create_access_token(data={"sub": db_user.username})
    refresh_token = create_refresh_token(data={"sub": db_user.username})
    
    return AuthResponse(
        code=200,
        msg="登录成功",
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    )

# 密码重置请求接口
@router.post("/auth/reset-password-request")
async def reset_password_request(request: PasswordResetRequest, db: Session = Depends(get_db)):
    # 检查手机号是否存在
    user = db.query(User).filter(User.phone == request.phone).first()
    if not user:
        return AuthResponse(
            code=404,
            msg="手机号未注册",
            data={}
        )
    
    # 这里可以添加发送验证码的逻辑
    return AuthResponse(
        code=200,
        msg="密码重置请求已接收，请检查手机验证码",
        data={}
    )

# 密码重置接口
@router.post("/auth/reset-password")
async def reset_password(reset: PasswordReset, db: Session = Depends(get_db)):
    # 检查手机号是否存在
    user = db.query(User).filter(User.phone == reset.phone).first()
    if not user:
        return AuthResponse(
            code=404,
            msg="手机号未注册",
            data={}
        )
    
    # 更新密码
    hashed_password = get_password_hash(reset.new_password)
    user.password = hashed_password
    db.commit()
    
    return AuthResponse(
        code=200,
        msg="密码重置成功",
        data={}
    )

# 获取当前用户信息
@router.get("/auth/me")
async def get_current_user_info(db: Session = Depends(get_db)):
    # 这里需要实现JWT认证，暂时返回示例数据
    return AuthResponse(
        code=200,
        msg="获取成功",
        data={
            "id": 1,
            "username": "test",
            "phone": "13800138000"
        }
    )