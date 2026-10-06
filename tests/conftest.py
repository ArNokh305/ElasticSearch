import uuid

import pytest
from elasticsearch.helpers import async_bulk
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.config import settings
from app.db import Base, async_session_maker, engine
from app.es import close_es_client, get_es_client
from app.main import app
from app.models import Document
from app.es_mapping import ensure_index


@pytest.fixture(scope="session", autouse=True)
async def _setup_infra():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    es = get_es_client()
    if await es.indices.exists(index=settings.es_index_name):
        await es.indices.delete(index=settings.es_index_name)
    await ensure_index(es, settings.es_index_name)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # re-fetch: the app lifespan may have closed and replaced the client
    es = get_es_client()
    if await es.indices.exists(index=settings.es_index_name):
        await es.indices.delete(index=settings.es_index_name)
    await close_es_client()
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_between_tests():
    yield
    async with async_session_maker() as session:
        await session.execute(delete(Document))
        await session.commit()

    es = get_es_client()
    await es.delete_by_query(
        index=settings.es_index_name,
        query={"match_all": {}},
        conflicts="proceed",
        refresh=True,
    )


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def seed_documents():
    async def _seed(docs: list[dict]) -> list[uuid.UUID]:
        ids: list[uuid.UUID] = []
        async with async_session_maker() as session:
            for doc in docs:
                doc_id = doc.get("id", uuid.uuid4())
                ids.append(doc_id)
                session.add(
                    Document(
                        id=doc_id,
                        text=doc["text"],
                        rubrics=doc.get("rubrics", []),
                        created_date=doc["created_date"],
                    )
                )
            await session.commit()

        es = get_es_client()
        actions = [
            {
                "_index": settings.es_index_name,
                "_id": str(doc_id),
                "_source": {"id": str(doc_id), "text": doc["text"]},
            }
            for doc_id, doc in zip(ids, docs, strict=True)
        ]
        await async_bulk(es, actions)
        await es.indices.refresh(index=settings.es_index_name)
        return ids

    return _seed
