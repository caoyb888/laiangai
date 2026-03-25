from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    doc_a_id: str = Field(..., description="文档 A 的 ID")
    doc_b_id: str = Field(..., description="文档 B 的 ID")
    task_name: str | None = Field(None, max_length=256, description="任务名称（可选）")
