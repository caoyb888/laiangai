from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.username == username, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def update_last_login(self, user_id: str) -> None:
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )

    async def create(
        self,
        *,
        id: str,
        username: str,
        display_name: str,
        hashed_password: str,
        department: str | None = None,
        role: str = "viewer",
    ) -> User:
        user = User(
            id=id,
            username=username,
            display_name=display_name,
            hashed_password=hashed_password,
            department=department,
            role=role,
        )
        self.db.add(user)
        await self.db.flush()
        return user
