from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.class_selection import ClassSelection
from pydantic import BaseModel

router = APIRouter()

# 请求和响应模型
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

# 职业选择接口
@router.post("/class/select")
async def select_class(class_data: ClassSelectionRequest, db: Session = Depends(get_db)):
    class_name = class_data.class_name
    
    valid_classes = ["变量巫师", "逻辑骑士", "循环射手"]
    if class_name not in valid_classes:
        return ClassSelectionResponse(
            code=400,
            msg="无效的职业选择",
            data={}
        )
    
    # 保存职业选择
    new_selection = ClassSelection(class_name=class_name)
    db.add(new_selection)
    db.commit()
    db.refresh(new_selection)
    
    return ClassSelectionResponse(
        code=200,
        msg="职业选择成功",
        data={
            "id": new_selection.id,
            "class_name": new_selection.class_name,
            "created_at": new_selection.created_at
        }
    )

# 获取职业选择记录
@router.get("/class/records")
async def get_class_records(db: Session = Depends(get_db)):
    records = db.query(ClassSelection).order_by(ClassSelection.created_at.desc()).all()
    
    # 转换为字典列表
    records_list = [
        {
            "id": record.id,
            "class_name": record.class_name,
            "created_at": record.created_at
        }
        for record in records
    ]
    
    return ClassRecordsResponse(
        code=200,
        msg="获取成功",
        data=records_list
    )