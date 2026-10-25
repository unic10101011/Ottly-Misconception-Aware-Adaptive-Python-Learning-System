from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import (
    auth_fingerprint,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.core.database import get_db
from app.models.user import User
from app.models.user import AIChatRecord
from app.models.class_selection import ClassSelection
from app.models.learning_submission import LearningSubmission
from app.models.learning_review import LearningReview
from app.models.guide_progress import GuideProgress
from app.models.generated_problem import GeneratedProblem
from app.models.settings import UserSettings, NotificationPreferences, LanguageSettings


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


class AccountUpdate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    phone: str = Field(min_length=6, max_length=20)
    current_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class AccountDelete(BaseModel):
    current_password: str


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
    token_data = {"sub": str(db_user.id), "v": auth_fingerprint(db_user)}
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


@router.patch("/auth/me")
def update_account(request: AccountUpdate, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user.id).with_for_update().first()
    if user is None:
        raise HTTPException(status_code=401, detail="账号已注销")
    if not verify_password(request.current_password, user.password):
        raise HTTPException(status_code=403, detail="当前密码错误")
    username = request.username.strip()
    phone = request.phone.strip()
    if len(username) < 2 or len(phone) < 6:
        raise HTTPException(status_code=422, detail="用户名或手机号格式不正确")
    if db.query(User).filter(User.username == username, User.id != user.id).first():
        raise HTTPException(status_code=409, detail="用户名已存在")
    if db.query(User).filter(User.phone == phone, User.id != user.id).first():
        raise HTTPException(status_code=409, detail="手机号已被注册")
    user.username = username
    user.phone = phone
    db.commit()
    token_data = {"sub": str(user.id), "v": auth_fingerprint(user)}
    return AuthResponse(data={
        "id": user.id, "username": user.username, "phone": user.phone,
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
    })


@router.post("/auth/change-password")
def change_password(request: PasswordChange, current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user.id).with_for_update().first()
    if user is None:
        raise HTTPException(status_code=401, detail="账号已注销")
    if not verify_password(request.current_password, user.password):
        raise HTTPException(status_code=403, detail="当前密码错误")
    if request.current_password == request.new_password:
        raise HTTPException(status_code=422, detail="新密码不能与当前密码相同")
    user.password = get_password_hash(request.new_password)
    db.commit()
    return AuthResponse(data={})


@router.delete("/auth/me")
def delete_account(request: AccountDelete, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    user_id = current_user.id
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if user is None:
        raise HTTPException(status_code=401, detail="账号已注销")
    if not verify_password(request.current_password, user.password):
        raise HTTPException(status_code=403, detail="当前密码错误")
    settings_ids = [row.id for row in db.query(UserSettings.id).filter(UserSettings.user_id == user_id)]
    if settings_ids:
        db.query(NotificationPreferences).filter(NotificationPreferences.user_settings_id.in_(settings_ids)).delete(synchronize_session=False)
        db.query(LanguageSettings).filter(LanguageSettings.user_settings_id.in_(settings_ids)).delete(synchronize_session=False)
    db.query(UserSettings).filter(UserSettings.user_id == user_id).delete(synchronize_session=False)
    db.query(LearningReview).filter(LearningReview.user_id == user_id).delete(synchronize_session=False)
    db.query(GuideProgress).filter(GuideProgress.user_id == user_id).delete(synchronize_session=False)
    db.query(LearningSubmission).filter(LearningSubmission.user_id == user_id).delete(synchronize_session=False)
    db.query(GeneratedProblem).filter(GeneratedProblem.user_id == user_id).delete(synchronize_session=False)
    db.query(AIChatRecord).filter(AIChatRecord.user_id == user_id).delete(synchronize_session=False)
    db.query(ClassSelection).filter(ClassSelection.user_id == user_id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    return AuthResponse(data={})
