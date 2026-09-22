from typing import Any, List, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def paginate(
    db: Session,
    query: Select,
    page: int = 1,
    page_size: int = 25,
) -> Tuple[List[Any], int]:
    """Applies offset/limit pagination to a SQLAlchemy select query and returns (items, total_count)."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 25
    if page_size > 100:
        page_size = 100

    # Calculate total count efficiently
    total_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = db.scalar(total_query) or 0

    offset = (page - 1) * page_size
    items = db.scalars(query.offset(offset).limit(page_size)).all()

    return list(items), total
