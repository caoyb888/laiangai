import uuid
from datetime import datetime
from sqlalchemy import select, func, insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.compare_task import CompareTask, DiffItem, TaskStatus, DiffLevel, DiffType


class CompareRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_task(
        self,
        *,
        creator_id: str,
        doc_a_id: str,
        doc_b_id: str,
        task_name: str | None = None,
    ) -> CompareTask:
        task = CompareTask(
            creator_id=creator_id,
            doc_a_id=doc_a_id,
            doc_b_id=doc_b_id,
            task_name=task_name,
            status=TaskStatus.PENDING,
            progress=0,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def get_task(self, task_id: str) -> CompareTask | None:
        result = await self.db.execute(
            select(CompareTask).where(
                CompareTask.id == task_id,
                CompareTask.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int | None = None,
        error_msg: str | None = None,
    ) -> None:
        task = await self.get_task(task_id)
        if not task:
            return
        task.status = status
        if progress is not None:
            task.progress = progress
        if error_msg is not None:
            task.error_msg = error_msg
        if status == TaskStatus.PROCESSING and task.started_at is None:
            task.started_at = datetime.utcnow()
        await self.db.flush()

    async def finish_task(
        self,
        task_id: str,
        total_diffs: int,
        critical_diffs: int,
    ) -> None:
        task = await self.get_task(task_id)
        if not task:
            return
        task.status = TaskStatus.DONE
        task.progress = 100
        task.total_diffs = total_diffs
        task.critical_diffs = critical_diffs
        task.finished_at = datetime.utcnow()
        await self.db.flush()

    async def batch_save_diffs(self, items: list[dict]) -> None:
        """批量写入差异条目，见 CLAUDE.md §5.3"""
        if not items:
            return
        # 确保每条记录 DiffType/DiffLevel 值合法
        for item in items:
            raw_type = item.get("diff_type", "modify")
            item["diff_type"] = raw_type if raw_type in DiffType.__members__.values() else DiffType.MODIFY.value
            raw_level = item.get("diff_level", "MINOR")
            item["diff_level"] = raw_level if raw_level in DiffLevel.__members__.values() else DiffLevel.MINOR.value

        await self.db.execute(insert(DiffItem), items)
        await self.db.flush()

    async def list_tasks(
        self,
        creator_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CompareTask], int]:
        base = (
            select(CompareTask)
            .where(CompareTask.creator_id == creator_id, CompareTask.is_deleted == False)
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()
        items_result = await self.db.execute(
            base.order_by(CompareTask.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(items_result.scalars().all()), total

    async def list_diffs(
        self,
        task_id: str,
        diff_level: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[DiffItem], int]:
        base = select(DiffItem).where(DiffItem.task_id == task_id)
        if diff_level:
            base = base.where(DiffItem.diff_level == diff_level)

        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        items_result = await self.db.execute(
            base.order_by(DiffItem.seq_no)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(items_result.scalars().all()), total
