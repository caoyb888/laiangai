import json
from app.core.db import AsyncSessionLocal
from app.repositories.document_repo import DocumentRepository
from app.models.document import FileType, ParseStatus
from .docx_parser import DocxParser
from .pdf_parser import PdfParser
from .ocr_parser import OcrParser
from .txt_parser import TxtParser
from .base import ParsedDocument
import structlog

logger = structlog.get_logger()

_parsers: dict[FileType, DocxParser | PdfParser | TxtParser] = {
    FileType.DOCX: DocxParser(),
    FileType.DOC:  DocxParser(),   # doc 先转换，统一用 docx 解析器
    FileType.PDF:  PdfParser(),
    FileType.TXT:  TxtParser(),
}


async def dispatch_parse(doc_id: str, content: bytes, file_type: FileType) -> None:
    """
    后台任务：分发解析，更新解析状态
    """
    async with AsyncSessionLocal() as db:
        repo = DocumentRepository(db)
        await repo.update_parse_status(doc_id, ParseStatus.PROCESSING)
        await db.commit()
        try:
            parser = _parsers.get(file_type)
            if not parser:
                raise ValueError(f"不支持的文件类型: {file_type}")

            doc_record = await repo.get_by_id(doc_id)
            parsed: ParsedDocument = await parser.parse(content, doc_record.file_name)

            # 持久化解析内容
            await repo.save_content(
                document_id=doc_id,
                raw_text=parsed.raw_text,
                structured_json=json.dumps(
                    _serialize_parsed(parsed), ensure_ascii=False
                ),
            )

            # 更新文档元数据，解析状态设为 DONE（与向量化解耦）
            await repo.update_meta(
                doc_id,
                title=parsed.meta.title,
                word_count=parsed.meta.word_count,
                page_count=parsed.meta.page_count,
                parse_status=ParseStatus.DONE,
            )
            await db.commit()
            logger.info("文档解析完成", doc_id=doc_id, file_type=file_type)

            # 向量化单独执行，失败不影响解析状态
            try:
                from app.services.vectorizer import vectorize_document
                await vectorize_document(doc_id, parsed)
            except Exception as vec_err:
                logger.warning("向量化失败（不影响解析结果，语义比对功能暂不可用）",
                               doc_id=doc_id, error=str(vec_err))

        except Exception as e:
            await repo.update_parse_status(doc_id, ParseStatus.FAILED, str(e))
            await db.commit()
            logger.error("文档解析失败", doc_id=doc_id, error=str(e))


def _serialize_parsed(parsed: ParsedDocument) -> dict:
    from dataclasses import asdict
    return asdict(parsed)
