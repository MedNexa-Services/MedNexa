from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

M = TypeVar("M")


async def paginate(
    db: AsyncSession, stmt: Select[M], limit: int, offset: int
) -> tuple[list[M], int]:
    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = list(await db.scalars(stmt.limit(limit).offset(offset)))
    return items, total or 0


def apply_updates(obj: Any, changes: dict[str, Any]) -> None:
    for field, value in changes.items():
        setattr(obj, field, value)
