from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import Base, engine
from app.es import close_es_client, get_es_client
from app.es_mapping import ensure_index
from app.routers.documents import router as documents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_index(get_es_client(), settings.es_index_name)
    yield
    await close_es_client()
    await engine.dispose()


app = FastAPI(
    title="Document Search Service",
    description=(
        "Simple full-text search service over documents: PostgreSQL stores "
        "the documents, Elasticsearch indexes their text for search."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(documents_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
