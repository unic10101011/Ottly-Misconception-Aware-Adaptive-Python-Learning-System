"""Store verified AI exercises and expose the owner's endless catalog category."""
from app.models.generated_problem import GeneratedProblem
from app.models.user import User
from app.services.problem_catalog import KNOWLEDGE, LEVELS, Lesson


def endless_lessons(db, user_id: int) -> list[Lesson]:
    rows = db.query(GeneratedProblem).filter_by(user_id=user_id).order_by(
        GeneratedProblem.created_at, GeneratedProblem.problem_id).all()
    return [Lesson.model_validate(row.lesson_json) for row in rows]


def save_verified_problem(db, user_id: int, lesson: Lesson, model: str) -> GeneratedProblem:
    """Call only after execution and semantic review; never overwrite a saved version."""
    lesson = Lesson.model_validate(lesson.model_dump(mode='json'))
    if (lesson.kind != 'endless' or not lesson.problem_id.startswith('endless-')
            or not lesson.published or any(key not in KNOWLEDGE for key in lesson.knowledge_ids)
            or set(lesson.prerequisite_problem_ids) != {slot.problem_id for slot in LEVELS}):
        raise ValueError('题目不符合无尽模式入库格式。')
    owner = db.query(User).filter_by(id=user_id, status='enabled').with_for_update().first()
    if owner is None:
        raise ValueError('账号不存在或已注销，本次题目未保存。')
    if db.get(GeneratedProblem, lesson.problem_id) is not None:
        raise ValueError('题目 ID 已存在，不能覆盖已保存版本。')
    record = GeneratedProblem(problem_id=lesson.problem_id, user_id=user_id,
                              lesson_json=lesson.model_dump(mode='json'), model=model)
    db.add(record)
    db.commit()
    return record
