import hashlib
from typing import TYPE_CHECKING, Any

from .models import IndexRequest, OrderContent, SearchHit, SearchRequest, SearchResponse

if TYPE_CHECKING:
    from .infrai_client import InfraiClient


class OrderSearch:
    def __init__(self, client: "InfraiClient", collection: str = "commerce-order-content"):
        self.client = client
        self.collection = collection

    async def prepare(self, dimension: int = 1536) -> None:
        await self.client.create_collection(self.collection, dimension)

    async def index(self, request: IndexRequest) -> int:
        embeddings = await self.client.embed([item.text for item in request.items])
        vectors = [self._vector(item, embedding) for item, embedding in zip(request.items, embeddings, strict=True)]
        stable_ids = ",".join(sorted(item.event_id for item in request.items))
        batch_id = "order-events:" + hashlib.sha256(stable_ids.encode()).hexdigest()
        await self.client.upsert(self.collection, vectors, batch_id)
        return len(vectors)

    async def search(self, request: SearchRequest) -> SearchResponse:
        embedding = (await self.client.embed([request.query]))[0]
        metadata_filter = {"kind": request.kind.value} if request.kind else None
        recalled = await self.client.query(
            self.collection,
            embedding,
            max(request.top_k * 3, request.top_k),
            metadata_filter,
        )
        matches = recalled.get("matches", [])
        if not matches:
            return SearchResponse(query=request.query, hits=[])

        candidates = [match["metadata"]["text"] for match in matches]
        ranked = await self.client.rerank(request.query, candidates, request.top_k)
        results = ranked.get("results", [])
        hits = [self._hit(matches[item["index"]], item.get("score")) for item in results]
        return SearchResponse(query=request.query, hits=hits)

    @staticmethod
    def _vector(item: OrderContent, embedding: list[float]) -> dict[str, Any]:
        return {
            "id": item.event_id,
            "values": embedding,
            "metadata": {
                "event_id": item.event_id,
                "order_id": item.order_id,
                "kind": item.kind.value,
                "text": item.text,
            },
        }

    @staticmethod
    def _hit(match: dict[str, Any], rerank_score: float | None) -> SearchHit:
        metadata = match["metadata"]
        return SearchHit(
            event_id=metadata["event_id"],
            order_id=metadata["order_id"],
            kind=metadata["kind"],
            text=metadata["text"],
            score=rerank_score,
        )
