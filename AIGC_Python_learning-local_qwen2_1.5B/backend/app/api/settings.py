from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.settings import UserSettings, NotificationPreferences, LanguageSettings
from pydantic import BaseModel

router = APIRouter()

# 请求和响应模型
class UserSettingsCreate(BaseModel):
    user_id: int
    eye_protection: bool = False
    volume: int = 50

class UserSettingsUpdate(BaseModel):
    eye_protection: bool = False
    volume: int = 50

class UserSettingsResponse(BaseModel):
    id: int
    user_id: int
    eye_protection: bool
    volume: int

class NotificationPreferencesUpdate(BaseModel):
    email_notifications: bool = True
    push_notifications: bool = True
    sms_notifications: bool = False

class NotificationPreferencesResponse(BaseModel):
    id: int
    user_settings_id: int
    email_notifications: bool
    push_notifications: bool
    sms_notifications: bool

class LanguageSettingsUpdate(BaseModel):
    language: str = "zh-CN"
    timezone: str = "Asia/Shanghai"

class LanguageSettingsResponse(BaseModel):
    id: int
    user_settings_id: int
    language: str
    timezone: str

class SettingsResponse(BaseModel):
    code: int = 200
    msg: str = "操作成功"
    data: dict

# 获取用户设置
@router.get("/settings/{user_id}")
async def get_user_settings(user_id: int, db: Session = Depends(get_db)):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        return SettingsResponse(
            code=404,
            msg=f"User settings not found for user_id: {user_id}",
            data={}
        )
    
    # 获取通知偏好
    notifications = db.query(NotificationPreferences).filter(
        NotificationPreferences.user_settings_id == settings.id
    ).first()
    
    # 获取语言设置
    language = db.query(LanguageSettings).filter(
        LanguageSettings.user_settings_id == settings.id
    ).first()
    
    return SettingsResponse(
        code=200,
        msg="获取成功",
        data={
            "settings": {
                "id": settings.id,
                "user_id": settings.user_id,
                "eye_protection": settings.eye_protection,
                "volume": settings.volume
            },
            "notifications": notifications.__dict__ if notifications else None,
            "language": language.__dict__ if language else None
        }
    )

# 创建用户设置
@router.post("/settings")
async def create_settings(settings: UserSettingsCreate, db: Session = Depends(get_db)):
    # 检查是否已存在
    existing = db.query(UserSettings).filter(UserSettings.user_id == settings.user_id).first()
    if existing:
        return SettingsResponse(
            code=400,
            msg="User settings already exist",
            data={}
        )
    
    # 创建用户设置
    new_settings = UserSettings(
        user_id=settings.user_id,
        eye_protection=settings.eye_protection,
        volume=settings.volume
    )
    db.add(new_settings)
    db.commit()
    db.refresh(new_settings)
    
    # 创建默认通知偏好
    new_notifications = NotificationPreferences(user_settings_id=new_settings.id)
    db.add(new_notifications)
    
    # 创建默认语言设置
    new_language = LanguageSettings(user_settings_id=new_settings.id)
    db.add(new_language)
    
    db.commit()
    
    return SettingsResponse(
        code=201,
        msg="创建成功",
        data={
            "id": new_settings.id,
            "user_id": new_settings.user_id,
            "eye_protection": new_settings.eye_protection,
            "volume": new_settings.volume
        }
    )

# 更新用户设置
@router.put("/settings/{user_id}")
async def update_settings(user_id: int, settings: UserSettingsUpdate, db: Session = Depends(get_db)):
    db_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not db_settings:
        return SettingsResponse(
            code=404,
            msg=f"User settings not found for user_id: {user_id}",
            data={}
        )
    
    # 更新设置
    db_settings.eye_protection = settings.eye_protection
    db_settings.volume = settings.volume
    db.commit()
    db.refresh(db_settings)
    
    return SettingsResponse(
        code=200,
        msg="更新成功",
        data={
            "id": db_settings.id,
            "user_id": db_settings.user_id,
            "eye_protection": db_settings.eye_protection,
            "volume": db_settings.volume
        }
    )

# 获取用户通知偏好
@router.get("/settings/{user_id}/notifications")
async def get_notifications(user_id: int, db: Session = Depends(get_db)):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        return SettingsResponse(
            code=404,
            msg=f"User settings not found for user_id: {user_id}",
            data={}
        )
    
    preferences = db.query(NotificationPreferences).filter(
        NotificationPreferences.user_settings_id == settings.id
    ).first()
    
    if not preferences:
        return SettingsResponse(
            code=404,
            msg="Notification preferences not found",
            data={}
        )
    
    return SettingsResponse(
        code=200,
        msg="获取成功",
        data=preferences.__dict__
    )

# 更新用户通知偏好
@router.put("/settings/{user_id}/notifications")
async def update_notifications(user_id: int, preferences: NotificationPreferencesUpdate, db: Session = Depends(get_db)):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        return SettingsResponse(
            code=404,
            msg=f"User settings not found for user_id: {user_id}",
            data={}
        )
    
    db_preferences = db.query(NotificationPreferences).filter(
        NotificationPreferences.user_settings_id == settings.id
    ).first()
    
    if not db_preferences:
        return SettingsResponse(
            code=404,
            msg="Notification preferences not found",
            data={}
        )
    
    # 更新通知偏好
    db_preferences.email_notifications = preferences.email_notifications
    db_preferences.push_notifications = preferences.push_notifications
    db_preferences.sms_notifications = preferences.sms_notifications
    db.commit()
    db.refresh(db_preferences)
    
    return SettingsResponse(
        code=200,
        msg="更新成功",
        data=db_preferences.__dict__
    )

# 获取用户语言设置
@router.get("/settings/{user_id}/language")
async def get_language(user_id: int, db: Session = Depends(get_db)):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        return SettingsResponse(
            code=404,
            msg=f"User settings not found for user_id: {user_id}",
            data={}
        )
    
    language_settings = db.query(LanguageSettings).filter(
        LanguageSettings.user_settings_id == settings.id
    ).first()
    
    if not language_settings:
        return SettingsResponse(
            code=404,
            msg="Language settings not found",
            data={}
        )
    
    return SettingsResponse(
        code=200,
        msg="获取成功",
        data=language_settings.__dict__
    )

# 更新用户语言设置
@router.put("/settings/{user_id}/language")
async def update_language(user_id: int, language: LanguageSettingsUpdate, db: Session = Depends(get_db)):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        return SettingsResponse(
            code=404,
            msg=f"User settings not found for user_id: {user_id}",
            data={}
        )
    
    db_language = db.query(LanguageSettings).filter(
        LanguageSettings.user_settings_id == settings.id
    ).first()
    
    if not db_language:
        return SettingsResponse(
            code=404,
            msg="Language settings not found",
            data={}
        )
    
    # 更新语言设置
    db_language.language = language.language
    db_language.timezone = language.timezone
    db.commit()
    db.refresh(db_language)
    
    return SettingsResponse(
        code=200,
        msg="更新成功",
        data=db_language.__dict__
    )