import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rubrics: list[str]
    text: str
    created_date: datetime


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[DocumentOut]


class DeleteResponse(BaseModel):
    id: uuid.UUID
    deleted_from_db: bool
    deleted_from_index: bool
