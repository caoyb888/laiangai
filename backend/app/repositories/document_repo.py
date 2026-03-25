import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document, DocumentContent, ParseStatus, FileType


class DocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, doc_id: str) -> Document | None:
        result = await self.db.execute(
            select(Document).where(Document.id == doc_id, Document.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_checksum(self, md5: str, uploader_id: str) -> Document | None:
        """MD5 去重，仅在同一上传用户范围内检查"""
        result = await self.db.execute(
            select(Document).where(
                Document.checksum_md5 == md5,
                Document.uploader_id == uploader_id,
                Document.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        id: str,
        uploader_id: str,
        file_name: str,
        file_type: FileType,
        file_size: int,
        minio_key: str,
        checksum_md5: str,
        category: str = "other",
    ) -> Document:
        doc = Document(
            id=id,
            uploader_id=uploader_id,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            minio_key=minio_key,
            checksum_md5=checksum_md5,
            category=category,
            parse_status=ParseStatus.PENDING,
        )
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def update_parse_status(
        self,
        doc_id: str,
        status: ParseStatus,
        *,
        error: str | None = None,
        title: str | None = None,
        word_count: int | None = None,
        page_count: int | None = None,
    ) -> None:
        doc = await self.get_by_id(doc_id)
        if not doc:
            return
        doc.parse_status = status
        if error is not None:
            doc.parse_error = error
        if title is not None:
            doc.title = title
        if word_count is not None:
            doc.word_count = word_count
        if page_count is not None:
            doc.page_count = page_count
        await self.db.flush()

    async def list_by_user(
        self,
        uploader_id: str,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
    ) -> tuple[list[Document], int]:
        base = select(Document).where(
            Document.uploader_id == uploader_id,
            Document.is_deleted == False,
        )
        if category:
            base = base.where(Document.category == category)

        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        items_result = await self.db.execute(
            base.order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(items_result.scalars().all()), total

    async def save_content(
        self,
        document_id: str,
        raw_text: str,
        structured_json: str,
        vector_ids: str | None = None,
    ) -> DocumentContent:
        existing = await self.db.execute(
            select(DocumentContent).where(DocumentContent.document_id == document_id)
        )
        content = existing.scalar_one_or_none()
        if content:
            content.raw_text = raw_text
            content.structured_json = structured_json
            if vector_ids is not None:
                content.vector_ids = vector_ids
        else:
            content = DocumentContent(
                id=str(uuid.uuid4()),
                document_id=document_id,
                raw_text=raw_text,
                structured_json=structured_json,
                vector_ids=vector_ids,
            )
            self.db.add(content)
        await self.db.flush()
        return content

    async def get_content(self, document_id: str) -> DocumentContent | None:
        result = await self.db.execute(
            select(DocumentContent).where(DocumentContent.document_id == document_id)
        )
        return result.scalar_one_or_none()
