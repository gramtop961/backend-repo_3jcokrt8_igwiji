import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from typing import List, Optional, Any, Dict
from bson import ObjectId
from pydantic import BaseModel, Field

from database import db, create_document, get_documents
from schemas import MenuCategory, Dish, Order, OrderItem

app = FastAPI(title="Restaurant Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------
# Helpers
# ------------------------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def to_str_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc["id"] = str(doc.get("_id"))
    doc.pop("_id", None)
    # Convert nested id fields if present
    if "items" in doc and isinstance(doc["items"], list):
        for it in doc["items"]:
            if isinstance(it, dict) and "dish_id" in it:
                it["dish_id"] = str(it["dish_id"]) if not isinstance(it["dish_id"], str) else it["dish_id"]
    return doc


# ------------------------
# Root & Health
# ------------------------
@app.get("/")
def read_root():
    return {"message": "Restaurant Management Backend Running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# ------------------------
# Menu: Categories
# ------------------------
@app.get("/api/menu/categories")
def list_categories():
    cats = get_documents("menucategory")
    return [to_str_id(c) for c in cats]

@app.post("/api/menu/categories", status_code=201)
def create_category(payload: MenuCategory):
    cat_id = create_document("menucategory", payload)
    doc = db["menucategory"].find_one({"_id": ObjectId(cat_id)})
    return to_str_id(doc)


# ------------------------
# Menu: Dishes
# ------------------------
@app.get("/api/menu/dishes")
def list_dishes(category_id: Optional[str] = None):
    filter_dict: Dict[str, Any] = {}
    if category_id:
        try:
            filter_dict["category_id"] = category_id
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid category_id")
    dishes = get_documents("dish", filter_dict)
    return [to_str_id(d) for d in dishes]

@app.post("/api/menu/dishes", status_code=201)
def create_dish(payload: Dish):
    # ensure referenced category exists
    if not db["menucategory"].find_one({"_id": ObjectId(payload.category_id)}):
        raise HTTPException(status_code=404, detail="Category not found")
    inserted_id = create_document("dish", payload)
    doc = db["dish"].find_one({"_id": ObjectId(inserted_id)})
    return to_str_id(doc)


# ------------------------
# Orders
# ------------------------
class CreateOrderRequest(BaseModel):
    table_number: str
    placed_by: str = Field(..., pattern="^(user|waiter)$")
    items: List[OrderItem]
    pay_now: bool = False
    payment_method: Optional[str] = Field(None, description="cash|card|online")
    notes: Optional[str] = None

@app.get("/api/orders")
def list_orders(status: Optional[str] = None, table_number: Optional[str] = None):
    filt: Dict[str, Any] = {}
    if status:
        filt["status"] = status
    if table_number:
        filt["table_number"] = table_number
    orders = get_documents("order", filt)
    # sort newest first
    orders = sorted(orders, key=lambda x: x.get("created_at"), reverse=True)
    return [to_str_id(o) for o in orders]

@app.post("/api/orders", status_code=201)
def create_order(req: CreateOrderRequest):
    # Validate dishes and denormalize names/prices
    enriched_items = []
    for it in req.items:
        dish_doc = db["dish"].find_one({"_id": ObjectId(it.dish_id)})
        if not dish_doc:
            raise HTTPException(status_code=404, detail=f"Dish not found: {it.dish_id}")
        if not dish_doc.get("is_available", True):
            raise HTTPException(status_code=400, detail=f"Dish not available: {dish_doc.get('name')}")
        enriched_items.append({
            "dish_id": dish_doc["_id"],
            "name": it.name or dish_doc.get("name"),
            "price": it.price or dish_doc.get("price"),
            "quantity": it.quantity,
            "notes": it.notes,
        })

    order_doc = {
        "table_number": req.table_number,
        "placed_by": req.placed_by,
        "items": enriched_items,
        "status": "pending",
        "paid": bool(req.pay_now),
        "payment_method": req.payment_method if req.pay_now else None,
        "notes": req.notes,
    }

    inserted_id = db["order"].insert_one(order_doc).inserted_id
    saved = db["order"].find_one({"_id": inserted_id})
    return to_str_id(saved)

@app.get("/api/orders/summary")
def order_summary(order_id: str):
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order id")
    doc = db["order"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    total = 0.0
    for it in doc.get("items", []):
        total += float(it.get("price", 0)) * int(it.get("quantity", 1))
    return {"id": str(doc["_id"]), "table_number": doc.get("table_number"), "total": round(total, 2), "paid": doc.get("paid", False), "status": doc.get("status")}

class UpdateStatusRequest(BaseModel):
    status: str = Field(..., description="pending|in_progress|ready|served|cancelled")

@app.patch("/api/orders/{order_id}/status")
def update_order_status(order_id: str, payload: UpdateStatusRequest):
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order id")
    res = db["order"].update_one({"_id": oid}, {"$set": {"status": payload.status}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    doc = db["order"].find_one({"_id": oid})
    return to_str_id(doc)

class PayOrderRequest(BaseModel):
    payment_method: str = Field(..., description="cash|card|online")

@app.patch("/api/orders/{order_id}/pay")
def pay_order(order_id: str, payload: PayOrderRequest):
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order id")
    res = db["order"].update_one({"_id": oid}, {"$set": {"paid": True, "payment_method": payload.payment_method}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    doc = db["order"].find_one({"_id": oid})
    return to_str_id(doc)


# ------------------------
# Kitchen board helpers
# ------------------------
@app.get("/api/kitchen/queue")
def kitchen_queue():
    # pending or in_progress for kitchen
    orders = list(db["order"].find({"status": {"$in": ["pending", "in_progress"]}}).sort("created_at", -1))
    return [to_str_id(o) for o in orders]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
