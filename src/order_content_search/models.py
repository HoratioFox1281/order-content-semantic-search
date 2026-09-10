from enum import StrEnum

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # Keep the domain search path usable in the test-only environment.
    class _Field:
        def __init__(self, default=... , **constraints):
            self.default, self.constraints = default, constraints

    def Field(default=..., **constraints):
        return _Field(default, **constraints)

    class BaseModel:
        def __init__(self, **values):
            annotations = getattr(type(self), "__annotations__", {})
            for name, annotation in annotations.items():
                field = getattr(type(self), name, ...)
                value = values.get(name, field.default if isinstance(field, _Field) else field)
                if value is ...:
                    raise ValueError(f"{name} is required")
                enum_type = ContentKind if name == "kind" else annotation
                if isinstance(enum_type, type) and issubclass(enum_type, StrEnum) and isinstance(value, str):
                    value = enum_type(value)
                if isinstance(field, _Field):
                    size = len(value) if hasattr(value, "__len__") else None
                    if size is not None and field.constraints.get("min_length", 0) > size:
                        raise ValueError(f"{name} is too short")
                setattr(self, name, value)


class ContentKind(StrEnum):
    CHECKOUT = "checkout"
    FULFILLMENT = "fulfillment"
    RECEIPT = "receipt"
    ORDER_UPDATE = "order_update"


class OrderContent(BaseModel):
    event_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    kind: ContentKind
    text: str = Field(min_length=1)


class IndexRequest(BaseModel):
    items: list[OrderContent] = Field(min_length=1, max_length=100)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=20)
    kind: ContentKind | None = None


class SearchHit(BaseModel):
    event_id: str
    order_id: str
    kind: ContentKind
    text: str
    score: float | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
