import io as io_module
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.db import get_db
from app.core.minio_client import get_minio
from app.core.security import get_current_user
from app.repositories.compare_repo import CompareRepository
from app.repositories.document_repo import DocumentRepository
from app.schemas.response import ApiResponse, ErrorCode
from app.services.report_gen import ReportGenerator

router = APIRouter()
settings = get_settings()

# 内存缓存：report_id -> (bucket, minio_key, content_type, filename)
# 生产环境可改为 Redis，此处用进程内字典（15分钟内有效）
_report_cache: dict[str, tuple[str, str, str, str]] = {}


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

    doc_repo = DocumentRepository(db)
    doc_a = await doc_repo.get_by_id(task.doc_a_id)
    doc_b = await doc_repo.get_by_id(task.doc_b_id)

    items, _ = await repo.list_diffs(task_id, page=1, page_size=9999)
    summary = {
        "total_diffs": task.total_diffs or 0,
        "critical_diffs": task.critical_diffs or 0,
        "major_diffs": sum(1 for i in items if i.diff_level == "MAJOR"),
        "minor_diffs": sum(1 for i in items if i.diff_level == "MINOR"),
    }
    report_data = {
        "task_name": task.task_name or task_id,
        "doc_a_name": doc_a.file_name if doc_a else task.doc_a_id,
        "doc_b_name": doc_b.file_name if doc_b else task.doc_b_id,
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

    safe_name = (task.task_name or task_id).replace("/", "_").replace(" ", "_")
    filename = f"比对报告_{safe_name}.{ext}"
    _report_cache[report_id] = (settings.minio_bucket_reports, minio_key, content_type, filename)

    # 返回后端代理下载 URL（禁止直接暴露 MinIO 地址，见 CLAUDE.md §4.4）
    # 注意：前端 axios baseURL 已含 /api/v1，此处只返回相对路径部分
    download_url = f"/reports/download/{report_id}"
    return ApiResponse.ok(data={
        "report_id": report_id,
        "download_url": download_url,
        "expires_in": 900,
    })


@router.get("/download/{report_id}")
async def download_report(
    report_id: str,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """后端代理下载报告，前端不直接访问 MinIO"""
    entry = _report_cache.get(report_id)
    if not entry:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="报告不存在或已过期")

    bucket, minio_key, content_type, filename = entry
    minio = get_minio()
    response = minio.get_object(bucket, minio_key)
    data = response.read()
    response.close()
    response.release_conn()

    from urllib.parse import quote
    return StreamingResponse(
        io_module.BytesIO(data),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
