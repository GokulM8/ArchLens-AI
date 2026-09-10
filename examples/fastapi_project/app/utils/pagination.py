"""Pagination utilities."""

from typing import Optional, TypeVar, Generic, List

T = TypeVar("T")


class Page(Generic[T]):
    """A paginated result set."""

    def __init__(
        self,
        items: List[T],
        total: int,
        page: int,
        page_size: int,
    ):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size

    @property
    def has_next(self) -> bool:
        return self.total > self.page * self.page_size

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def total_pages(self) -> int:
        """Total number of pages."""
        if self.total == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


def paginate_results(
    items: List[T],
    total: int,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
) -> Page[T]:
    """Paginate a list of results."""
    return Page(items=items, total=total, page=page, page_size=page_size)