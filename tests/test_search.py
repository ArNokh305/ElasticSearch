from datetime import datetime, timedelta

from app.config import settings

BASE_DATE = datetime(2024, 1, 1, 12, 0, 0)


def _doc(i: int, text: str) -> dict:
    return {"text": text, "created_date": BASE_DATE + timedelta(days=i), "rubrics": []}


async def test_search_returns_ordered_and_limited(client, seed_documents):
    docs = [_doc(i, f"пример уникальный документ номер {i}") for i in range(25)]
    ids = await seed_documents(docs)

    response = await client.get("/documents/search", params={"q": "уникальный"})
    assert response.status_code == 200
    body = response.json()

    assert body["count"] == 20
    dates = [item["created_date"] for item in body["results"]]
    assert dates == sorted(dates, reverse=True)
    # all 25 fit in the overfetch window, so these must be exactly the 20 newest
    newest_first = [str(doc_id) for doc_id in reversed(ids)][:20]
    assert [item["id"] for item in body["results"]] == newest_first
    assert all("уникальный" in item["text"] for item in body["results"])


async def test_search_no_matches(client, seed_documents):
    await seed_documents([_doc(0, "совершенно другой текст без совпадений")])

    response = await client.get("/documents/search", params={"q": "нетсовпадений12345"})
    assert response.status_code == 200
    body = response.json()
    assert body == {"query": "нетсовпадений12345", "count": 0, "results": []}


async def test_search_respects_overfetch_window(client, seed_documents, monkeypatch):
    # Force a small overfetch window to make the ES-relevance-window
    # boundary observable: seeding more matching docs than the window
    # must still cap how many candidates ES hands back, even though 20
    # is the final result cap.
    overfetch = 5
    monkeypatch.setattr(settings, "search_overfetch_size", overfetch)

    docs = [_doc(i, f"граничныйтест слово {i}") for i in range(overfetch + 5)]
    await seed_documents(docs)

    response = await client.get("/documents/search", params={"q": "граничныйтест"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] <= overfetch


async def test_search_requires_query(client):
    response = await client.get("/documents/search", params={"q": ""})
    assert response.status_code == 422
