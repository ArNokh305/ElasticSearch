import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


async def get_newest_by_ids(
    session: AsyncSession, ids: list[uuid.UUID], limit: int
) -> list[Document]:
    if not ids:
        return []
    result = await session.execute(
        select(Document)
        .where(Document.id.in_(ids))
        .order_by(Document.created_date.desc(), Document.id)
        .limit(limit)
    )
    return list(result.scalars().all())


async def delete_by_id(session: AsyncSession, doc_id: uuid.UUID) -> bool:
    result = await session.execute(delete(Document).where(Document.id == doc_id))
    return result.rowcount > 0
