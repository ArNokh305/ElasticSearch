import argparse
import ast
import asyncio
import csv
import sys
import uuid
from collections.abc import Sequence
from datetime import datetime
from itertools import batched

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from sqlalchemy import delete

from app.config import settings
from app.db import Base, async_session_maker, engine
from app.models import Document
from app.es_mapping import ensure_index

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_rubrics(raw: str, row_number: int) -> list[str]:
    try:
        value = ast.literal_eval(raw)
        if isinstance(value, list):
            return [str(item) for item in value]
        print(f"warning: row {row_number}: rubrics is not a list, got {type(value)}; using []")
        return []
    except (ValueError, SyntaxError):
        print(f"warning: row {row_number}: could not parse rubrics {raw!r}; using []")
        return []


def read_rows(csv_path: str):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_number, row in enumerate(reader, start=1):
            yield {
                "id": uuid.uuid4(),
                "text": row["text"],
                "created_date": datetime.strptime(row["created_date"], DATE_FORMAT),
                "rubrics": parse_rubrics(row["rubrics"], row_number),
            }


async def flush_batch(
    batch: Sequence[dict], session, es: AsyncElasticsearch
) -> None:
    session.add_all([Document(**row) for row in batch])
    await session.commit()

    actions = [
        {
            "_index": settings.es_index_name,
            "_id": str(row["id"]),
            "_source": {"id": str(row["id"]), "text": row["text"]},
        }
        for row in batch
    ]
    await async_bulk(es, actions)


async def main(csv_path: str, batch_size: int, truncate: bool) -> None:
    es = AsyncElasticsearch(settings.elasticsearch_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        if truncate:
            async with async_session_maker() as session:
                await session.execute(delete(Document))
                await session.commit()
            if await es.indices.exists(index=settings.es_index_name):
                await es.indices.delete(index=settings.es_index_name)

        await ensure_index(es, settings.es_index_name)

        total = 0
        async with async_session_maker() as session:
            for batch in batched(read_rows(csv_path), batch_size):
                await flush_batch(batch, session, es)
                total += len(batch)
                print(f"imported {total} rows...")

        print(f"done: imported {total} rows total")
    finally:
        await es.close()
        await engine.dispose()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-path", default="posts.csv")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Clear the documents table and recreate the ES index before importing",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    asyncio.run(main(args.csv_path, args.batch_size, args.truncate))
