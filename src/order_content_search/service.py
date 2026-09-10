from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .infrai_client import InfraiClient, InfraiError
from .models import IndexRequest, SearchRequest, SearchResponse
from .order_search import OrderSearch


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = InfraiClient()
    app.state.search = OrderSearch(client)
    yield
    await client.close()


app = FastAPI(title="Order content search", lifespan=lifespan)


@app.exception_handler(InfraiError)
async def infrai_error_handler(_request: Request, error: InfraiError):
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return JSONResponse(
        status_code=status,
        content={"detail": {"code": error.code, "message": str(error)}},
    )


@app.post("/admin/prepare", status_code=204)
async def prepare(request: Request) -> None:
    await request.app.state.search.prepare()


@app.post("/order-content", status_code=202)
async def index_order_content(body: IndexRequest, request: Request) -> dict[str, int]:
    indexed = await request.app.state.search.index(body)
    return {"indexed": indexed}


@app.post("/search", response_model=SearchResponse)
async def search_order_content(body: SearchRequest, request: Request) -> SearchResponse:
    return await request.app.state.search.search(body)
