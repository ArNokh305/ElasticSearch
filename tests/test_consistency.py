from datetime import datetime

from app.config import settings
from app.db import async_session_maker
from app.es import get_es_client
from app.models import Document


async def test_indexed_document_matches_db_row(client, seed_documents):
    [doc_id] = await seed_documents(
        [{"text": "согласованность данных между хранилищами", "created_date": datetime(2024, 1, 1)}]
    )

    es = get_es_client()
    es_doc = await es.get(index=settings.es_index_name, id=str(doc_id))

    async with async_session_maker() as session:
        db_doc = await session.get(Document, doc_id)

    assert es_doc["_source"]["id"] == str(doc_id)
    assert es_doc["_source"]["text"] == db_doc.text


async def test_delete_leaves_no_orphan_in_either_store(client, seed_documents):
    [doc_id] = await seed_documents(
        [{"text": "запись без сирот после удаления", "created_date": datetime(2024, 1, 1)}]
    )

    response = await client.delete(f"/documents/{doc_id}")
    assert response.status_code == 200

    async with async_session_maker() as session:
        assert await session.get(Document, doc_id) is None

    es = get_es_client()
    assert not await es.exists(index=settings.es_index_name, id=str(doc_id))
