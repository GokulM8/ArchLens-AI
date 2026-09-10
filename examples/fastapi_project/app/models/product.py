"""Product model with Pydantic and SQLAlchemy."""

from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ProductCategory(str, Enum):
    """Product category enumeration."""

    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    BOOKS = "books"
    HOME = "home"
    SPORTS = "sports"


class Product(Base):
    """SQLAlchemy Product model."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    description = Column(String(1000), nullable=True)
    price = Column(Float, nullable=False)
    category = Column(String(50), index=True, nullable=False)
    stock_quantity = Column(Integer, default=0)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    owner = relationship("User", back_populates="products")


class ProductBase(BaseModel):
    """Base Pydantic model for Product."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    price: float = Field(..., gt=0)
    category: ProductCategory
    stock_quantity: int = Field(default=0, ge=0)


class ProductCreate(ProductBase):
    """Product creation model."""
    pass


class ProductUpdate(BaseModel):
    """Product update model."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    category: Optional[ProductCategory] = None
    stock_quantity: Optional[int] = Field(None, ge=0)


class ProductResponse(ProductBase):
    """Product response model."""

    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True