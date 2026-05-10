from typing import List, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
    message: str = "Success"
