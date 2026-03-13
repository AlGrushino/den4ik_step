from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Trade, TradeItem
from sqlalchemy.orm import aliased

from schemas import TradeRequest

from logger import logger
import json
from typing import List


from sqlalchemy import select, and_, case, or_
from models import PlayableCardDefinitions, ExclusiveCardDefinitions, ClipCardDefinitions, User
from schemas import PlayableCard, ExclusiveCard, ClipCard, ApiResponse, TradeInfo, AcceptTradeRequest, UserCardItem

from routers.cards import spend_user_cards, add_cards_to_user

router = APIRouter(prefix="/api/trades", tags=["trades"])

@router.post("/create_trade", response_model=ApiResponse)
async def create_trade_endpoint(request: TradeRequest, db: AsyncSession = Depends(get_db)):
    """Create single trade"""
    try:
        logger.info(f"Creating trade: {request.from_id} -> {request.to_id}")

        # ✅ 1. model_dump() → list[dict] → json.dumps() → строка
        from_cards_json = json.dumps([card.model_dump() for card in request.from_cards])
        to_cards_json = json.dumps([card.model_dump() for card in request.to_cards])

        logger.info(from_cards_json)
        logger.info(to_cards_json)

        trade = Trade(
            from_id=request.from_id,
            to_id=request.to_id
        )
        db.add(trade)
        await db.flush()  # Получить trade_id
        trade_id = trade.trade_id

        all_cards = [TradeItem(
                trade_id=trade_id,
                side='from',
                type_id=item.type_id,
                card_id=item.card_id,
                variant_key=item.variant_key,  # auto → JSONB
                quantity=item.quantity
            ) for item in request.from_cards]
        
        all_cards += [TradeItem(
                trade_id=trade_id,
                side='to',
                type_id=item.type_id,
                card_id=item.card_id,
                variant_key=item.variant_key,  # auto → JSONB
                quantity=item.quantity
            ) for item in request.to_cards]
        
        logger.info(f"{all_cards}")
        
        db.add_all(all_cards)
        
        return ApiResponse[int](success=True, data=trade_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trade failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Trade error")
    
@router.get("/get_user_trades/{user_id}")
async def get_user_trades(user_id: int, db: AsyncSession = Depends(get_db)):
    try:
        UserFrom = aliased(User)
        UserTo = aliased(User)
        
        stmt = select(
            Trade.trade_id,
            Trade.from_id,
            Trade.to_id,
            UserFrom.username.label('from_username'),  # ✅ UserFrom вместо User1
            UserTo.username.label('to_username')       # ✅ UserTo вместо User2
        ).select_from(Trade).outerjoin(
            UserFrom,                    # ✅ Используем алиас
            Trade.from_id == UserFrom.user_id
        ).outerjoin(
            UserTo,                      # ✅ Используем алиас  
            Trade.to_id == UserTo.user_id
        ).where(
            or_(
                Trade.from_id == user_id,
                Trade.to_id == user_id
            )
        ).order_by(Trade.trade_id.desc())

        result = await db.execute(stmt)
        rows = result.fetchall()
        
        trades = []
        for row in rows:
            trade_id, from_id, to_id, from_username, to_username = row
            trades.append(TradeInfo(
                trade_id=trade_id,
                from_id=from_id,
                to_id=to_id,
                from_username=from_username or "Unknown",
                to_username=to_username or "Unknown"
            ))
        
        logger.info(f"{trades}")

        return ApiResponse[List[TradeInfo]](success=True, data=trades)

    except Exception as e:
        logger.info(str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
def row_to_dict(row):
    return dict(row._mapping) if row else None
    
@router.post("/accept_trade")
async def accept_trade(request: AcceptTradeRequest, db: AsyncSession = Depends(get_db)):
    to_id = request.to_id
    stmt = select(
        Trade.from_id
    ).where(
        Trade.trade_id == request.trade_id,
        Trade.to_id == to_id
    )
    from_id = (await db.execute(stmt)).scalar_one_or_none()
    if from_id is None:
        raise HTTPException(status_code=404, detail=str("Trade not found"))
    stmt = select(TradeItem).where(
        TradeItem.trade_id == request.trade_id
    ).order_by(TradeItem.side)
    rows = (await db.execute(stmt)).scalars().all()
    logger.info(f"{rows}")
    from_cards = [
        UserCardItem(
            type_id=card.type_id,
            card_id=card.card_id,
            variant_key=card.variant_key,
            quantity=card.quantity
        ) 
        for card in rows 
        if card.side == 'from'
    ]
    
    to_cards = [
        UserCardItem(
            type_id=card.type_id,
            card_id=card.card_id,
            variant_key=card.variant_key,
            quantity=card.quantity
        ) 
        for card in rows 
        if card.side == 'to'
    ]
    from_missing = await spend_user_cards(db, from_id, from_cards)
    to_missing = await spend_user_cards(db, to_id, to_cards)
    logger.info(f"missing:\n{from_cards}\n\n{to_cards}")
    if from_missing or to_missing:
        missing_data = {
            'from_missing': row_to_dict(from_missing[0]) if from_missing else None,
            'to_missing': row_to_dict(to_missing[0]) if to_missing else None
        }

        raise HTTPException(status_code=500, detail=missing_data)
    
    logger.info("Adding cards")
    await add_cards_to_user(db, from_id, to_cards)
    await add_cards_to_user(db, to_id, from_cards)
    logger.info("Trade success")
    return ApiResponse[bool](success=True, data=True)

    
@router.get("/trade/{trade_id}", response_model=ApiResponse)
async def get_trade_cards(trade_id: int, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(
            TradeItem.side,
            TradeItem.type_id,
            TradeItem.card_id,
            TradeItem.quantity,
            TradeItem.variant_key
        ).select_from(
            TradeItem
        ).where(
            TradeItem.trade_id == trade_id,
            TradeItem.quantity > 0
        ).order_by(TradeItem.side, TradeItem.card_id)

        rows = (await db.execute(stmt)).fetchall()
    
        from_data = []
        to_data = []
        for row in rows:
            card_dict = dict(row._mapping)
            if(card_dict['side'] == 'from'):
                from_data.append(card_dict)
            else:
                to_data.append(card_dict)

        result = {"from":from_data,"to":to_data}

        logger.info(f'{result}')
        
        return ApiResponse[dict](success=True, data=result)
        
        # ✅ Простая группировка
        from_cards = []
        to_cards = []
        
        logger.info(f"{rows}")

        for row in rows:
            side, type_id, card_id, quantity, variant_key, png_name, category, description = row
            
            card_data = {
                'card_id': card_id,
                'png_name': png_name,
                'quantity': quantity,
                'variant_key': variant_key
            }
            
            if side == 'from':
                if type_id == 1:  # Playable
                    from_cards.append(PlayableCard(**card_data, category=category))
                elif type_id == 2:  # Exclusive
                    from_cards.append(ExclusiveCard(**card_data))
                elif type_id == 3:  # Clip
                    from_cards.append(ClipCard(**card_data, description=description))
            else:  # 'to'
                # Аналогично для to_cards...
                if type_id == 1:
                    to_cards.append(PlayableCard(**card_data, category=category))
                elif type_id == 2:
                    to_cards.append(ExclusiveCard(**card_data))
                elif type_id == 3:
                    to_cards.append(ClipCard(**card_data, description=description))
        
        return ApiResponse(success=True, data=[{
            "from_cards": from_cards,
            "to_cards": to_cards
        }])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

