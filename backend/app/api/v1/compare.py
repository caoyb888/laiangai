from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import get_current_user
from app.repositories.compare_repo import CompareRepository
from app.repositories.document_repo import DocumentRepository
from app.schemas.compare import CreateTaskRequest
from app.schemas.response import ApiResponse, ErrorCode
from app.tasks.compare_task import run_compare_pipeline
from app.core.audit import log_operation

router = APIRouter()


@router.get("/tasks", response_model=ApiResponse[dict])
async def list_compare_tasks(
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    repo = CompareRepository(db)
    tasks, total = await repo.list_tasks(current_user["user_id"], page, page_size)
    return ApiResponse.ok(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "task_id": t.id,
                "task_name": t.task_name,
                "status": t.status,
                "progress": t.progress,
                "total_diffs": t.total_diffs,
                "critical_diffs": t.critical_diffs,
                "created_at": t.created_at.isoformat(),
                "finished_at": t.finished_at.isoformat() if t.finished_at else None,
            }
            for t in tasks
        ],
    })


@router.post("/tasks", response_model=ApiResponse[dict])
async def create_compare_task(
    req: CreateTaskRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    doc_repo = CompareRepository(db)
    # 校验两个文档存在且解析完成
    for doc_id in [req.doc_a_id, req.doc_b_id]:
        doc = await DocumentRepository(db).get_by_id(doc_id)
        if not doc or doc.is_deleted:
            return ApiResponse.error(ErrorCode.DOCUMENT_NOT_FOUND, f"文档 {doc_id} 不存在")
        if doc.parse_status != "done":
            return ApiResponse.error(ErrorCode.DOCUMENT_PARSE_FAILED,
                                      f"文档 {doc_id} 尚未解析完成，状态: {doc.parse_status}")

    task = await doc_repo.create_task(
        creator_id=current_user["user_id"],
        doc_a_id=req.doc_a_id,
        doc_b_id=req.doc_b_id,
        task_name=req.task_name,
    )
    await log_operation(db, current_user["user_id"], "CREATE_TASK", "compare_task", task.id)
    await db.commit()  # 必须在 background_tasks 前提交，否则后台任务查不到记录
    background_tasks.add_task(
        run_compare_pipeline,
        task.id,
        current_user["user_id"],
    )
    return ApiResponse.ok(data={"task_id": task.id, "status": "pending"}, message="比对任务已创建")


@router.get("/tasks/{task_id}", response_model=ApiResponse[dict])
async def get_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    repo = CompareRepository(db)
    doc_repo = DocumentRepository(db)
    task = await repo.get_task(task_id)
    if not task:
        return ApiResponse.error(ErrorCode.TASK_NOT_FOUND, "任务不存在")
    doc_a = await doc_repo.get_by_id(task.doc_a_id)
    doc_b = await doc_repo.get_by_id(task.doc_b_id)
    return ApiResponse.ok(data={
        "task_id": task.id,
        "task_name": task.task_name,
        "status": task.status,
        "progress": task.progress,
        "total_diffs": task.total_diffs,
        "critical_diffs": task.critical_diffs,
        "error_msg": task.error_msg,
        "doc_a_name": doc_a.file_name if doc_a else task.doc_a_id,
        "doc_b_name": doc_b.file_name if doc_b else task.doc_b_id,
        "created_at": task.created_at.isoformat(),
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    })


@router.get("/tasks/{task_id}/diffs", response_model=ApiResponse[dict])
async def get_diff_items(
    task_id: str,
    diff_level: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    repo = CompareRepository(db)
    items, total = await repo.list_diffs(task_id, diff_level, page, page_size)
    return ApiResponse.ok(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {
                "id": item.id,
                "seq_no": item.seq_no,
                "diff_type": item.diff_type,
                "diff_level": item.diff_level,
                "doc_a_section": item.doc_a_section,
                "doc_a_text": item.doc_a_text,
                "doc_b_section": item.doc_b_section,
                "doc_b_text": item.doc_b_text,
                "semantic_desc": item.semantic_desc,
                "risk_keywords": item.risk_keywords,
                "is_reviewed": item.is_reviewed,
            }
            for item in items
        ],
    })
