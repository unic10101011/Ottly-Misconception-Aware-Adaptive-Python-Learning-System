from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.class_selection import ClassSelection
from app.models.user import User


router = APIRouter()


class ClassSelectionRequest(BaseModel):
    class_name: str


class ClassSelectionResponse(BaseModel):
    code: int = 200
    msg: str = "操作成功"
    data: dict


class ClassRecordsResponse(BaseModel):
    code: int = 200
    msg: str = "获取成功"
    data: list


@router.post("/class/select")
async def select_class(
    class_data: ClassSelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if class_data.class_name not in ["变量巫师", "逻辑骑士", "循环射手"]:
        return ClassSelectionResponse(code=400, msg="无效的职业选择", data={})
    selection = ClassSelection(user_id=current_user.id, class_name=class_data.class_name)
    db.add(selection)
    db.commit()
    db.refresh(selection)
    return ClassSelectionResponse(
        code=200,
        msg="职业选择成功",
        data={
            "id": selection.id,
            "class_name": selection.class_name,
            "created_at": selection.created_at,
        },
    )


@router.get("/class/records")
async def get_class_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = db.query(ClassSelection).filter(
        ClassSelection.user_id == current_user.id
    ).order_by(ClassSelection.created_at.desc()).all()
    return ClassRecordsResponse(
        code=200,
        msg="获取成功",
        data=[
            {
                "id": record.id,
                "class_name": record.class_name,
                "created_at": record.created_at,
            }
            for record in records
        ],
    )
