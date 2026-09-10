"""Product API routes."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.product import ProductCreate, ProductUpdate, ProductResponse
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])
product_service = ProductService()


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(product: ProductCreate):
    """Create a new product."""
    return await product_service.create_product(product, owner_id=1)  # TODO: get from auth


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int):
    """Get a product by ID."""
    product = await product_service.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/", response_model=List[ProductResponse])
async def get_products(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """Get list of products with optional filtering."""
    return await product_service.get_products(skip=skip, limit=limit, category=category)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, product: ProductUpdate):
    """Update a product."""
    updated = await product_service.update_product(product_id, product)
    if updated is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return updated


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int):
    """Delete a product."""
    deleted = await product_service.delete_product(product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found")
    return None


@router.patch("/{product_id}/stock")
async def update_stock(product_id: int, quantity_change: int):
    """Update product stock."""
    product = await product_service.update_stock(product_id, quantity_change)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product