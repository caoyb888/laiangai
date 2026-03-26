"""
LLM 统一调用客户端
- 主用：通义千问（DashScope）
- 备用：DeepSeek（OpenAI 兼容接口）
- 含：脱敏标记校验 / 重试 / 主备切换 / 审计日志
见 CLAUDE.md §2.2, §5.5
"""
import time
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import get_settings
from app.services.desensitizer import DesensitizedChunk
import structlog

logger = structlog.get_logger()
settings = get_settings()

# 运行时覆盖（None 表示跟随 settings.llm_api_mock）
_runtime_mock: bool | None = None


def get_llm_mock_mode() -> bool:
    if _runtime_mock is not None:
        return _runtime_mock
    return settings.llm_api_mock


def set_llm_mock_mode(value: bool) -> None:
    global _runtime_mock
    _runtime_mock = value


# ── Prompt 模板（全部从文件加载，禁止在业务代码硬编码）───────────────────────
def _load_prompt(name: str) -> str:
    import os
    path = os.path.join(os.path.dirname(__file__), "prompts", f"{name}.txt")
    with open(path, encoding="utf-8") as f:
        return f.read()


class LLMAPIError(Exception):
    pass


class LLMTimeoutError(LLMAPIError):
    pass


class LLMClient:
    """
    见 CLAUDE.md §5.5：
    MAX_CHUNK_TOKENS = 2000
    MAX_RETRY = 3
    TIMEOUT_SECONDS = 30
    """
    MAX_CHUNK_TOKENS = 2000
    MAX_RETRY        = 3
    TIMEOUT_SECONDS  = 30

    @classmethod
    async def analyze_diff(
        cls,
        chunks: list[DesensitizedChunk],
        task_id: str = "",
        user_id: str = "",
    ) -> list[dict]:
        """
        对差异块列表进行语义分析
        返回每个 chunk 的分析结果：semantic_desc, diff_level, risk_keywords
        """
        # ── 脱敏标记校验（见 CLAUDE.md §4.1）──────────────────────────────
        for chunk in chunks:
            if not chunk.is_desensitized:
                raise ValueError(
                    "LLMClient 拒绝处理未脱敏内容！"
                    "必须先调用 desensitizer.desensitize() 并确保 is_desensitized=True"
                )

        results = []
        for chunk in chunks:
            result = await cls._call_with_retry(
                chunk.text, task_id=task_id, user_id=user_id
            )
            results.append(result)
        return results

    @classmethod
    @retry(
        stop=stop_after_attempt(MAX_RETRY),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(LLMAPIError),
    )
    async def _call_with_retry(
        cls,
        text: str,
        task_id: str = "",
        user_id: str = "",
    ) -> dict:
        """主备切换逻辑：主 API 失败后自动切换到备用"""
        provider = settings.llm_primary_provider
        started_at = time.time()
        status = "success"
        error_code = None

        try:
            if get_llm_mock_mode():
                return cls._mock_response(text)

            if provider == "qianwen":
                result = await cls._call_qianwen(text)
            else:
                result = await cls._call_deepseek(text)

            return result

        except asyncio.TimeoutError:
            status = "timeout"
            error_code = "TIMEOUT"
            raise LLMTimeoutError(f"{provider} API 超时")
        except Exception as e:
            status = "failed"
            error_code = type(e).__name__
            # 尝试切换备用
            if provider == "qianwen":
                logger.warning("通义千问 API 失败，切换到 DeepSeek", error=str(e))
                try:
                    return await cls._call_deepseek(text)
                except Exception as e2:
                    raise LLMAPIError(f"主备 API 均失败: {e2}") from e2
            raise LLMAPIError(str(e)) from e
        finally:
            latency = int((time.time() - started_at) * 1000)
            await cls._write_audit_log(
                user_id=user_id,
                task_id=task_id,
                provider=provider,
                latency_ms=latency,
                status=status,
                error_code=error_code,
            )

    @classmethod
    async def _call_qianwen(cls, text: str) -> dict:
        import dashscope
        from dashscope import Generation

        prompt_template = _load_prompt("diff_analysis")
        prompt = prompt_template.format(diff_text=text)

        response = await asyncio.wait_for(
            asyncio.to_thread(
                Generation.call,
                model="qwen-max",
                api_key=settings.llm_api_key_primary,
                prompt=prompt,
                max_tokens=512,
            ),
            timeout=cls.TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            raise LLMAPIError(f"通义千问返回错误: {response.code} {response.message}")

        return cls._parse_llm_response(response.output.text)

    @classmethod
    async def _call_deepseek(cls, text: str) -> dict:
        from openai import AsyncOpenAI

        prompt_template = _load_prompt("diff_analysis")
        prompt = prompt_template.format(diff_text=text)

        client = AsyncOpenAI(
            api_key=settings.llm_api_key_backup,
            base_url="https://api.deepseek.com/v1",
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0.1,
            ),
            timeout=cls.TIMEOUT_SECONDS,
        )
        return cls._parse_llm_response(response.choices[0].message.content)

    @classmethod
    def _parse_llm_response(cls, text: str) -> dict:
        """
        解析 LLM 返回的 JSON 格式
        Prompt 要求返回：{"diff_level": "...", "semantic_desc": "...", "risk_keywords": [...]}
        """
        import json
        import re
        # 提取 JSON 块
        match = re.search(r"\{.*?\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # 解析失败时返回默认值，不抛异常（容错）
        logger.warning("LLM 响应解析失败，使用默认值", raw=text[:200])
        return {
            "diff_level": "MINOR",
            "semantic_desc": text[:200],
            "risk_keywords": [],
        }

    @classmethod
    def _mock_response(cls, text: str) -> dict:
        """测试环境 Mock，见 CLAUDE.md §8.3"""
        return {
            "diff_level": "MAJOR",
            "semantic_desc": f"[MOCK] 检测到内容变更: {text[:50]}",
            "risk_keywords": ["[MOCK]"],
        }

    @classmethod
    async def _write_audit_log(
        cls,
        user_id: str,
        task_id: str,
        provider: str,
        latency_ms: int,
        status: str,
        error_code: str | None,
    ) -> None:
        """写入 LLM 调用审计日志，见 CLAUDE.md §4.3"""
        try:
            from app.core.db import AsyncSessionLocal
            from sqlalchemy import text as sa_text
            async with AsyncSessionLocal() as db:
                await db.execute(sa_text("""
                    INSERT INTO llm_audit_log
                      (user_id, task_id, provider, model_name,
                       latency_ms, status, error_code, desensitized)
                    VALUES (:user_id, :task_id, :provider, :model,
                            :latency, :status, :error_code, 1)
                """), {
                    "user_id": user_id or "system",
                    "task_id": task_id or None,
                    "provider": provider,
                    "model": "qwen-max" if provider == "qianwen" else "deepseek-chat",
                    "latency": latency_ms,
                    "status": status,
                    "error_code": error_code,
                })
                await db.commit()
        except Exception as e:
            # 审计日志失败不影响主流程，但必须记录错误
            logger.error("审计日志写入失败", error=str(e))
