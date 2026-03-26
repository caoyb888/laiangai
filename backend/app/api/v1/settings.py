"""
运行时配置接口（仅供管理/测试使用）
"""
from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.schemas.response import ApiResponse
from app.services.llm_client import get_llm_mock_mode, set_llm_mock_mode

router = APIRouter()


@router.get("/llm-mode", response_model=ApiResponse[dict])
async def get_llm_mode(
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict]:
    """获取当前 LLM 调用模式"""
    return ApiResponse.ok(data={"mock": get_llm_mock_mode()})


@router.post("/llm-mode", response_model=ApiResponse[dict])
async def set_llm_mode(
    mock: bool,
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict]:
    """切换 LLM 调用模式（mock=true 使用 Mock，mock=false 使用真实 API）"""
    set_llm_mock_mode(mock)
    return ApiResponse.ok(data={"mock": get_llm_mock_mode()})
