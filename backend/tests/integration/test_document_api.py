"""
文档管理接口集成测试
见 CLAUDE.md §8.1：api/v1/ 接口层覆盖率 ≥ 80%

注意：测试使用 SQLite（内存/文件）替代 MySQL，MinIO 全部 Mock。
      LLM_API_MOCK=true（由 tests/conftest.py 设置），禁止真实 LLM 调用。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
class TestDocumentAPI:

    async def test_upload_invalid_type(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """不允许的文件类型应被拒绝，返回 4001"""
        files = {"file": ("test.exe", b"fake content", "application/octet-stream")}
        resp = await client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        assert resp.status_code == 200          # FastAPI 返回 200，业务码在 body
        assert resp.json()["code"] == 4001      # FILE_TYPE_NOT_ALLOWED

    async def test_upload_requires_auth(self, client: AsyncClient) -> None:
        """未携带 Token 应返回 401"""
        files = {"file": ("test.docx", b"fake", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        resp = await client.post("/api/v1/documents/upload", files=files)
        assert resp.status_code == 401

    async def test_upload_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        sample_docx: bytes,
        mock_minio: MagicMock,
    ) -> None:
        """合法 .docx 文件应上传成功，返回 document_id"""
        with (
            patch("app.api.v1.documents.get_minio", return_value=mock_minio),
            patch("app.api.v1.documents.dispatch_parse", new_callable=AsyncMock),
        ):
            files = {
                "file": (
                    "test.docx",
                    sample_docx,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            }
            data = {"category": "contract"}
            resp = await client.post(
                "/api/v1/documents/upload",
                files=files,
                data=data,
                headers=auth_headers,
            )
        body = resp.json()
        assert body["code"] == 200
        assert "document_id" in body["data"]
        assert body["data"]["document_id"]  # 非空

    async def test_upload_pdf(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_minio: MagicMock,
    ) -> None:
        """PDF 文件类型合法，应通过类型校验"""
        # 使用最小合法 PDF 字节（仅验证类型校验通过，不验证解析）
        minimal_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        with (
            patch("app.api.v1.documents.get_minio", return_value=mock_minio),
            patch("app.api.v1.documents.dispatch_parse", new_callable=AsyncMock),
        ):
            files = {"file": ("test.pdf", minimal_pdf, "application/pdf")}
            data = {"category": "other"}
            resp = await client.post(
                "/api/v1/documents/upload",
                files=files,
                data=data,
                headers=auth_headers,
            )
        # 通过类型校验（可能因 MD5 或 DB 问题而报其他业务错误，但不应是 4001）
        assert resp.json()["code"] != 4001

    async def test_list_documents_requires_auth(self, client: AsyncClient) -> None:
        """文档列表接口未认证应返回 401"""
        resp = await client.get("/api/v1/documents/")
        assert resp.status_code == 401

    async def test_list_documents_returns_page_structure(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """文档列表接口返回结构包含分页字段"""
        resp = await client.get("/api/v1/documents/", headers=auth_headers)
        body = resp.json()
        assert body["code"] == 200
        assert "total" in body["data"]
        assert "items" in body["data"]
        assert "page" in body["data"]
