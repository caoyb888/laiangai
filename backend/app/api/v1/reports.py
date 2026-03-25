import io as io_module
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.db import get_db
from app.core.minio_client import get_minio, get_presigned_url
from app.core.security import get_current_user
from app.repositories.compare_repo import CompareRepository
from app.schemas.response import ApiResponse, ErrorCode
from app.services.report_gen import ReportGenerator

router = APIRouter()
settings = get_settings()


@router.post("/tasks/{task_id}/export", response_model=ApiResponse[dict])
async def export_report(
    task_id: str,
    format: str = "pdf",   # pdf | docx
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    if format not in ("pdf", "docx"):
        return ApiResponse.error(4000, "format 仅支持 pdf 或 docx")

    repo = CompareRepository(db)
    task = await repo.get_task(task_id)
    if not task:
        return ApiResponse.error(ErrorCode.TASK_NOT_FOUND, "任务不存在")

    items, _ = await repo.list_diffs(task_id, page=1, page_size=9999)
    summary = {
        "total_diffs": task.total_diffs or 0,
        "critical_diffs": task.critical_diffs or 0,
        "major_diffs": sum(1 for i in items if i.diff_level == "MAJOR"),
        "minor_diffs": sum(1 for i in items if i.diff_level == "MINOR"),
    }
    report_data = {
        "task_name": task.task_name or task_id,
        "summary": summary,
        "diff_items": [
            {
                "seq_no": i.seq_no, "diff_level": i.diff_level,
                "doc_a_text": i.doc_a_text, "doc_b_text": i.doc_b_text,
                "semantic_desc": i.semantic_desc, "risk_keywords": i.risk_keywords,
            }
            for i in items
        ],
    }
    gen = ReportGenerator()
    if format == "docx":
        content = await gen.generate_docx(report_data)
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = "docx"
    else:
        content = await gen.generate_pdf(report_data)
        content_type = "application/pdf"
        ext = "pdf"

    # 上传到 MinIO（见 CLAUDE.md §4.4）
    report_id = str(uuid.uuid4())
    minio_key = f"reports/{task_id}/{report_id}.{ext}"
    minio = get_minio()
    minio.put_object(
        settings.minio_bucket_reports, minio_key,
        io_module.BytesIO(content), len(content), content_type=content_type
    )

    # 生成有时效下载链接（≤ 15分钟，见 CLAUDE.md §4.4）
    download_url = get_presigned_url(settings.minio_bucket_reports, minio_key)

    return ApiResponse.ok(data={
        "report_id": report_id,
        "download_url": download_url,
        "expires_in": 900,
    })
