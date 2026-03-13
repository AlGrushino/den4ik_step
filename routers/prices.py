from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
from database import get_db

from models import PriceItem, UserDailyPurchase, DailyStore
from schemas import ApiResponse, PriceItemSchema, PurchaseRequest, UserDailyPurchases, PurchaseResponce, DailyShopCard


from logger import logger
import random, json

from routers.currency import spend_user_currency

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text

from routers.albums import add_album_page, create_custom_album

router = APIRouter(prefix="/api/shop", tags=["shop"])

@router.get("/daily_info", response_model=ApiResponse[List[DailyShopCard]])
async def get_daily_shop_cards(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DailyStore))
    cards = result.scalars().all()
    
    # Преобразуем ORM объекты в Pydantic модели
    daily_cards = [
        DailyShopCard(
            id=card.id,
            card_id=card.card_id,
            type_id=card.type_id,
            game_currency=card.game_currency
        )
        for card in cards
    ]
    
    return ApiResponse(success=True, data=daily_cards)

@router.get("/user_daily_purchases/{user_id}", response_model=ApiResponse[List[UserDailyPurchases]])
async def get_user_daily_purchases(
    user_id: int, 
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(UserDailyPurchase).where(
        UserDailyPurchase.user_id == user_id
    ))
    
    purchases = result.scalars().all()
    
    # Преобразуем ORM объекты в Pydantic модели
    user_purchases = [
        UserDailyPurchases(
            id=purchase.id,
            buy_id=purchase.buy_id
        )
        for purchase in purchases
    ]
    
    return ApiResponse(success=True, data=user_purchases)


@router.get("/prices", response_model=ApiResponse[List[PriceItemSchema]])
async def get_current_shop(db: AsyncSession = Depends(get_db)):
    logger.info("all")
    stmt = select(PriceItem).where(
        PriceItem.is_active == True,
    )

    result = await db.execute(stmt)
    
    return ApiResponse(success=True, data=result.scalars().all())

@router.post("/buy", response_model=ApiResponse[PurchaseResponce])
async def buy_item(request: PurchaseRequest, db: AsyncSession = Depends(get_db)):
    user_id = request.user_id
    code = request.code
    target_id = request.target_id
    payload = request.payload

    logger.info(f"code: {code} : target_id: {target_id}")

    stmt = select(PriceItem).where(and_(
            PriceItem.code == code,
            PriceItem.target_id == target_id,
            PriceItem.is_active == True,
        )
    )

    item = (await db.execute(stmt)).scalar_one_or_none()
        
    if not item:
        raise HTTPException(404, "Item not found")
    
    logger.info(f"item: {item.game_price} : {item.premium_price}")
    
    user_currency = await spend_user_currency(db, user_id, item.game_price, item.premium_price)
    result = await handle_purchase(db, code, user_id, payload)

    purchase_response = PurchaseResponce(
        game_currency=user_currency.game_currency,
        premium_currency=user_currency.premium_currency,
        result=result
    )
    
    return ApiResponse(success=True, data=purchase_response)

async def handle_purchase(db, code: str, user_id: int, payload: dict):
    handlers = {
        "ALBUM_PAGE": handle_album_page,
        "CUSTOM_ALBUM": handle_custom_album,
        # "PACK_GOLDEN": handle_pack_golden,
    }
    
    handler = handlers.get(code)
    if not handler:
        raise HTTPException(400, "Unknown purchase type")
    
    return await handler(db, user_id, payload)

async def handle_album_page(db: AsyncSession, user_id: int, payload: dict):
    album_id = payload["album_id"]

    return await add_album_page(db, user_id, album_id)

async def handle_custom_album(db: AsyncSession, user_id: int, payload: dict):
    return await create_custom_album(db, user_id)