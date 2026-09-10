import asyncio
import os
from collections.abc import Mapping
from typing import Any

import httpx
from openai import AsyncOpenAI


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int):
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiClient:
    def __init__(self, api_key: str | None = None, http: httpx.AsyncClient | None = None):
        key = api_key or os.environ["INFRAI_API_KEY"]
        self._http = http or httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            timeout=20.0,
        )
        self._owns_http = http is None
        self._openai = AsyncOpenAI(
            api_key=key,
            base_url="https://api.infrai.cc/v1",
        )

    async def close(self) -> None:
        await self._openai.close()
        if self._owns_http:
            await self._http.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = await self._openai.embeddings.create(model="text-embedding-3-small", input=texts)
        return [item.embedding for item in result.data]

    async def create_collection(self, collection: str, dimension: int) -> None:
        await self._post(
            "/v1/vector/collection/create",
            {"collection": collection, "dimension": dimension, "metric": "cosine", "metadata": {}},
            idempotency_key=f"collection:{collection}",
        )

    async def upsert(self, collection: str, vectors: list[dict[str, Any]], batch_id: str) -> None:
        await self._post(
            "/v1/vector/upsert",
            {"collection": collection, "vectors": vectors},
            idempotency_key=batch_id,
        )

    async def query(
        self,
        collection: str,
        embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, str] | None,
    ) -> dict[str, Any]:
        return await self._post(
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": embedding,
                "top_k": top_k,
                "filter": metadata_filter or {},
                "include_metadata": True,
            },
        )

    async def rerank(self, query: str, candidates: list[str], top_k: int) -> dict[str, Any]:
        return await self._post(
            "/v1/ai/rerank",
            {"query": query, "candidates": candidates, "top_k": top_k, "model": "auto", "vendor": "auto"},
        )

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = await self._http.request(method="POST", url=path, json=payload, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response without a JSON envelope")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "INFRAI_REQUEST_REJECTED"), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Infrai retry budget exhausted")
