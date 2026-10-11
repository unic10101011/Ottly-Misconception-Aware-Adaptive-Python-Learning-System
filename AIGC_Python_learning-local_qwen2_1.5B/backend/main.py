from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from app.api import auth, class_selection, settings, ai, coding
from app.core.database import engine, Base
# 导入模型类，确保SQLAlchemy知道需要创建哪些表
from app.models.user import User, AIChatRecord
from app.models.class_selection import ClassSelection
from app.models.settings import UserSettings, NotificationPreferences, LanguageSettings

# 创建数据库表
try:
    Base.metadata.create_all(bind=engine)
    print("建表成功")
except Exception as e:
    print(f"建表失败: {e}")

# 创建FastAPI应用
app = FastAPI(
    title="AIGC后端系统",
    description="整合认证、职业选择、设置和AI对话功能的后端系统",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
app.include_router(class_selection.router, prefix="/api/v1", tags=["职业选择"])
app.include_router(settings.router, prefix="/api/v1", tags=["设置"])
app.include_router(ai.router, prefix="/api/v1", tags=["AI对话"])
app.include_router(coding.router, prefix="/api/v1", tags=["代码执行"])

# 根路径
@app.get("/")
async def root():
    return {"message": "AIGC后端系统"}

# 健康检查
@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)