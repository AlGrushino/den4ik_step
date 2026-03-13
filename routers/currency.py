from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from typing import List, Tuple
from database import get_db

from models import UserCurrency
from schemas import ApiResponse, UserCurrencyInfo


from logger import logger
import random, json

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text

router = APIRouter(prefix="/api/currency", tags=["currency"])

async def spend_user_currency(db: AsyncSession, user_id: int, game_currency: int = 0, premium_currency: int = 0) -> UserCurrencyInfo:
    stmt = (
        update(UserCurrency)
        .where(
            UserCurrency.user_id == user_id,
            UserCurrency.game_currency >= game_currency,
            UserCurrency.premium_currency >= premium_currency
        )
        .values(
            game_currency=UserCurrency.game_currency - game_currency,
            premium_currency=UserCurrency.premium_currency - premium_currency
        )
        .returning(
            UserCurrency.game_currency,
            UserCurrency.premium_currency
        )
    )
    
    result = await db.execute(stmt)
    updated_row = result.fetchone()
    
    if not updated_row:
        raise HTTPException(400, "Недостаточно валюты")
    
    return UserCurrencyInfo(game_currency = updated_row.game_currency, premium_currency = updated_row.premium_currency)

@router.get("/get_currency/{user_id}", response_model=ApiResponse)
async def get_user_currency(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    logger.info("Get currency")
    stmt = select(
        UserCurrency
    ).where(
        UserCurrency.user_id == user_id
    )
    
    result = await db.execute(stmt)
    user_currency = result.scalars().first()

    logger.info(f"{user_currency.game_currency}")

    data = UserCurrencyInfo(
        game_currency=user_currency.game_currency,
        premium_currency=user_currency.premium_currency
    )

    return ApiResponse[UserCurrencyInfo](success=True, data=data)