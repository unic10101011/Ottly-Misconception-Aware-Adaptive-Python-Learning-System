from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from app.api import auth, class_selection, settings, ai, coding, learning_history, guides, endless
from app.core.database import engine, Base
# 导入模型类，确保SQLAlchemy知道需要创建哪些表
from app.models.user import User, AIChatRecord, UserProfile
from app.models.class_selection import ClassSelection
from app.models.settings import UserSettings, NotificationPreferences, LanguageSettings
from app.models.learning_submission import LearningSubmission
from app.models.learning_review import LearningReview
from app.models.guide_progress import GuideProgress
from app.models.generated_problem import GeneratedProblem

# 创建数据库表
Base.metadata.create_all(bind=engine)
from app.core.submission_migration import require_current_schema
require_current_schema(engine)

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
app.include_router(learning_history.router, prefix="/api/v1", tags=["学习记录"])
app.include_router(guides.router, prefix="/api/v1", tags=["知识引导"])
app.include_router(endless.router, prefix="/api/v1", tags=["无尽挑战"])

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
