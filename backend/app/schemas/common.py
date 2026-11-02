"""通用分页与响应包装。"""
from fastapi import Query
from pydantic import BaseModel


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从 1 开始"),
        page_size: int = Query(20, ge=1, le=500, description="每页条数"),
        keyword: str | None = Query(None, description="关键字（编码/名称模糊匹配）"),
    ):
        self.page = page
        self.page_size = page_size
        self.keyword = keyword

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class IdsPayload(BaseModel):
    ids: list[int]
