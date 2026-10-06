import uuid

from elasticsearch import AsyncElasticsearch
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repository import get_newest_by_ids
from app.schemas import DocumentOut

RESULT_LIMIT = 20


async def search_documents(
    query: str, session: AsyncSession, es: AsyncElasticsearch
) -> list[DocumentOut]:
    es_response = await es.search(
        index=settings.es_index_name,
        query={"match": {"text": query}},
        size=settings.search_overfetch_size,
        source=False,
    )
    ids = [uuid.UUID(hit["_id"]) for hit in es_response["hits"]["hits"]]
    documents = await get_newest_by_ids(session, ids, RESULT_LIMIT)
    return [DocumentOut.model_validate(doc) for doc in documents]
