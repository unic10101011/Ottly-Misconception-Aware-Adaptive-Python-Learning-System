from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.core.database import Base

class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    eye_protection = Column(Boolean, default=False)
    volume = Column(Integer, default=50)

class NotificationPreferences(Base):
    __tablename__ = "notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_settings_id = Column(Integer, ForeignKey("user_settings.id"), unique=True, nullable=False)
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    sms_notifications = Column(Boolean, default=False)

class LanguageSettings(Base):
    __tablename__ = "language_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_settings_id = Column(Integer, ForeignKey("user_settings.id"), unique=True, nullable=False)
    language = Column(String(10), default="zh-CN")
    timezone = Column(String(50), default="Asia/Shanghai")