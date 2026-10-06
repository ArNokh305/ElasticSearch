from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.es import get_es_client
from app.main import app


async def test_startup_creates_table_and_index(client):
    # A freshly started service (before any import) must answer searches
    # with an empty result rather than a 500 for a missing table/index.
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE documents"))
    await get_es_client().indices.delete(index=settings.es_index_name)

    async with app.router.lifespan_context(app):
        response = await client.get("/documents/search", params={"q": "что-нибудь"})

    assert response.status_code == 200
    assert response.json()["count"] == 0
