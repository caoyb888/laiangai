import hashlib
import io
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit import log_operation
from app.core.db import get_db
from app.core.minio_client import get_minio, get_presigned_url
from app.core.security import get_current_user
from app.models.document import FileType
from app.repositories.document_repo import DocumentRepository
from app.schemas.response import ApiResponse, ErrorCode
from app.services.parser.dispatcher import dispatch_parse
import structlog

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()

# 允许的 MIME 类型，见 CLAUDE.md §6.3
ALLOWED_MIME: dict[str, FileType] = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
    "application/msword": FileType.DOC,
    "application/pdf": FileType.PDF,
    "text/plain": FileType.TXT,
}

# 扩展名兜底（浏览器可能发送 application/octet-stream），见 CLAUDE.md §6.3
EXT_FALLBACK: dict[str, FileType] = {
    ".docx": FileType.DOCX,
    ".doc": FileType.DOC,
    ".pdf": FileType.PDF,
    ".txt": FileType.TXT,
}


@router.get("/", response_model=ApiResponse[dict])
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    repo = DocumentRepository(db)
    docs, total = await repo.list_by_user(
        current_user["user_id"], page, page_size, category
    )
    return ApiResponse.ok(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "document_id": d.id,
                "file_name": d.file_name,
                "file_type": d.file_type,
                "parse_status": d.parse_status,
                "category": d.category,
                "title": d.title,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
    })


@router.post("/upload", response_model=ApiResponse[dict])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(default="other"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    # 1. 文件类型校验：先查 MIME，再用扩展名兜底（浏览器可能发送 octet-stream）
    ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    file_type = ALLOWED_MIME.get(file.content_type or "") or EXT_FALLBACK.get(ext)
    if file_type is None:
        return ApiResponse.error(ErrorCode.FILE_TYPE_NOT_ALLOWED,
                                 f"不支持的文件类型: {file.content_type}")

    # 2. 文件大小校验
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        return ApiResponse.error(ErrorCode.FILE_TOO_LARGE,
                                 f"文件超出 {settings.max_file_size_mb}MB 限制")

    # 3. MD5 去重
    md5 = hashlib.md5(content).hexdigest()
    repo = DocumentRepository(db)
    existing = await repo.get_by_checksum(md5, current_user["user_id"])
    if existing:
        return ApiResponse.error(ErrorCode.DUPLICATE_FILE,
                                 f"文件已存在，文档ID: {existing.id}")

    # 4. 上传至 MinIO（见 CLAUDE.md §4.4，禁止存储在容器本地文件系统）
    doc_id = str(uuid.uuid4())
    minio_key = f"documents/{current_user['user_id']}/{doc_id}/{file.filename}"
    minio = get_minio()
    minio.put_object(
        settings.minio_bucket_documents, minio_key,
        io.BytesIO(content), len(content),
        content_type=file.content_type,
    )

    # 5. 创建文档记录
    doc = await repo.create(
        id=doc_id,
        uploader_id=current_user["user_id"],
        file_name=file.filename,
        file_type=file_type,
        file_size=len(content),
        minio_key=minio_key,
        checksum_md5=md5,
        category=category,
    )

    # 6. 后台异步解析（dispatch_parse 由任务6/7实现）
    background_tasks.add_task(dispatch_parse, doc_id, content, doc.file_type)

    await log_operation(db, current_user["user_id"], "UPLOAD_DOC",
                        "document", doc_id, {"file_name": file.filename})

    return ApiResponse.ok(data={
        "document_id": doc_id,
        "file_name": file.filename,
        "parse_status": "pending",
    }, message="上传成功，正在解析中")


@router.get("/{doc_id}", response_model=ApiResponse[dict])
async def get_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    repo = DocumentRepository(db)
    doc = await repo.get_by_id(doc_id)
    if not doc or doc.is_deleted:
        return ApiResponse.error(ErrorCode.DOCUMENT_NOT_FOUND, "文档不存在")

    # 生成有时效的下载链接（≤15分钟，见 CLAUDE.md §4.4）
    download_url = get_presigned_url(
        settings.minio_bucket_documents, doc.minio_key, expires_seconds=900
    )
    return ApiResponse.ok(data={
        "document_id": doc.id,
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "parse_status": doc.parse_status,
        "file_size": doc.file_size,
        "page_count": doc.page_count,
        "category": doc.category,
        "title": doc.title,
        "word_count": doc.word_count,
        "created_at": doc.created_at.isoformat(),
        "download_url": download_url,  # 有时效，前端不得缓存
    })
