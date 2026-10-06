import uuid
from datetime import datetime

from elasticsearch import ConnectionError as ESConnectionError
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.db import async_session_maker
from app.es import get_es_client
from app.main import app
from app.models import Document


async def test_delete_removes_from_db_and_index(client, seed_documents):
    [doc_id] = await seed_documents(
        [{"text": "документ на удаление", "created_date": datetime(2024, 1, 1), "rubrics": []}]
    )

    response = await client.delete(f"/documents/{doc_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["deleted_from_db"] is True
    assert body["deleted_from_index"] is True

    search_response = await client.get("/documents/search", params={"q": "удаление"})
    assert search_response.json()["count"] == 0

    es = get_es_client()
    assert not await es.exists(index=settings.es_index_name, id=str(doc_id))


async def test_delete_nonexistent_id_returns_404(client):
    response = await client.delete(f"/documents/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_delete_keeps_db_row_when_index_delete_fails(client, seed_documents):
    # If Elasticsearch is unavailable the DB delete must be rolled back;
    # otherwise the index keeps an orphan that a retry can never remove
    # (the retry would 404 on the already-deleted DB row).
    [doc_id] = await seed_documents(
        [{"text": "документ при сбое индекса", "created_date": datetime(2024, 1, 1)}]
    )

    class FailingES:
        async def delete(self, **kwargs):
            raise ESConnectionError("elasticsearch is down")

    app.dependency_overrides[get_es_client] = FailingES
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as failing_client:
            response = await failing_client.delete(f"/documents/{doc_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    async with async_session_maker() as session:
        assert await session.get(Document, doc_id) is not None

    retry = await client.delete(f"/documents/{doc_id}")
    assert retry.status_code == 200
    assert not await get_es_client().exists(index=settings.es_index_name, id=str(doc_id))
