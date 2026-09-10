import pytest

from order_content_search.models import SearchRequest
from order_content_search.order_search import OrderSearch


class StubClient:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.2, 0.8] for _text in texts]

    async def query(self, collection, embedding, top_k, metadata_filter):
        assert metadata_filter == {"kind": "fulfillment"}
        return {
            "matches": [
                {"metadata": {"event_id": "evt-receipt", "order_id": "A-42", "kind": "receipt", "text": "Receipt emailed"}},
                {"metadata": {"event_id": "evt-shipped", "order_id": "A-42", "kind": "fulfillment", "text": "Parcel left the warehouse"}},
            ]
        }

    async def rerank(self, query, candidates, top_k):
        assert query == "where is order A-42"
        assert candidates == ["Receipt emailed", "Parcel left the warehouse"]
        return {"results": [{"index": 1, "score": 0.97}]}


@pytest.mark.asyncio
async def test_fulfillment_question_returns_shipping_update():
    search = OrderSearch(StubClient())
    result = await search.search(
        SearchRequest(query="where is order A-42", kind="fulfillment", top_k=1)
    )

    assert result.hits[0].event_id == "evt-shipped"
    assert result.hits[0].order_id == "A-42"
    assert result.hits[0].kind == "fulfillment"
