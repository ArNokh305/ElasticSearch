import uuid

from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.es import get_es_client
from app.repository import delete_by_id
from app.schemas import DeleteResponse, SearchResponse
from app.search_service import search_documents

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Free-text search query"),
    session: AsyncSession = Depends(get_session),
    es: AsyncElasticsearch = Depends(get_es_client),
) -> SearchResponse:
    results = await search_documents(q, session, es)
    return SearchResponse(query=q, count=len(results), results=results)


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    es: AsyncElasticsearch = Depends(get_es_client),
) -> DeleteResponse:
    deleted_from_db = await delete_by_id(session, doc_id)
    if not deleted_from_db:
        raise HTTPException(status_code=404, detail="Document not found")

    deleted_from_index = True
    try:
        await es.delete(index=settings.es_index_name, id=str(doc_id))
    except NotFoundError:
        deleted_from_index = False

    await session.commit()
    return DeleteResponse(
        id=doc_id, deleted_from_db=deleted_from_db, deleted_from_index=deleted_from_index
    )
