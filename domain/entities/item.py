from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Item(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True