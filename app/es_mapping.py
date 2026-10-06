INDEX_BODY = {
    "settings": {
        "analysis": {
            "filter": {
                "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                "russian_stemmer": {"type": "stemmer", "language": "russian"},
            },
            "analyzer": {
                "ru_text_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "russian_stop", "russian_stemmer"],
                }
            },
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "text": {"type": "text", "analyzer": "ru_text_analyzer"},
        }
    },
}


async def ensure_index(es, index_name: str) -> None:
    if not await es.indices.exists(index=index_name):
        await es.indices.create(index=index_name, **INDEX_BODY)
