"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# Example schemas (kept for reference)

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Restaurant app schemas

class MenuCategory(BaseModel):
    name: str = Field(..., description="Category name, e.g., Starters")
    icon: Optional[str] = Field(None, description="Optional icon name for UI")
    description: Optional[str] = Field(None, description="Optional description")

class Dish(BaseModel):
    name: str = Field(..., description="Dish name")
    description: Optional[str] = Field(None)
    price: float = Field(..., ge=0, description="Unit price")
    category_id: str = Field(..., description="Related MenuCategory _id as string")
    is_available: bool = Field(True)

class OrderItem(BaseModel):
    dish_id: str = Field(..., description="Dish _id as string")
    name: Optional[str] = Field(None, description="Denormalized dish name for convenience")
    price: Optional[float] = Field(None, description="Denormalized unit price")
    quantity: int = Field(..., ge=1)
    notes: Optional[str] = Field(None, description="Special instructions")

class Order(BaseModel):
    table_number: str = Field(..., description="Table identifier, e.g., 12 or A1")
    placed_by: str = Field(..., description="user|waiter")
    items: List[OrderItem]
    status: str = Field("pending", description="pending|in_progress|ready|served|cancelled")
    paid: bool = Field(False)
    payment_method: Optional[str] = Field(None, description="cash|card|online")
    notes: Optional[str] = None

# Note: The Flames database viewer will automatically:
# 1. Read these schemas from GET /schema endpoint
# 2. Use them for document validation when creating/editing
# 3. Handle all database operations (CRUD) directly
# 4. You don't need to create any database endpoints!
