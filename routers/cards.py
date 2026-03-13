from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
from database import get_db
from models import UserCardCollection, PlayableCardDefinitions, ExclusiveCardDefinitions, ClipCardDefinitions, ArchiveItem, UserAlbum, AlbumCard, model_to_dict
from schemas import PlayableCard, ExclusiveCard, ClipCard, CardKey, ApiResponse

from schemas import CraftRequest, UserCardItem, CollectionWithSelectionRequest

from logger import logger
import random, json

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text

from sqlalchemy import select, null, union_all, literal_column
from sqlalchemy.orm import aliased

from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix="/api/collection", tags=["cards"])

# FINAL FIXED OPTIMIZED FUNCTIONS THAT WORK WITH POSTGRESQL

async def spend_user_cards(db: AsyncSession, user_id: int, cards: List[UserCardItem]) -> List[UserCardItem]:
    if not cards:
        return []
    
    
    values_list = []
    for i, card in enumerate(cards):
        variant_key_param = card.variant_key if isinstance(card.variant_key, dict) else json.loads(card.variant_key)
        
        
        values_list.append(f"({user_id}::bigint, {card.type_id}::int, {card.card_id}::int, '{json.dumps(variant_key_param)}'::jsonb, {card.quantity}::int)")
    
    values_clause = ", ".join(values_list)
        
    final_sql = f"""
    WITH input_cards(user_id, type_id, card_id, variant_key, needed_quantity) AS (
        VALUES {values_clause}
    )
    SELECT ic.*, COALESCE(ucc.quantity, 0) as current_quantity,
           ic.needed_quantity - COALESCE(ucc.quantity, 0) as deficit
    FROM input_cards ic
    LEFT JOIN user_card_collection ucc ON 
        ucc.user_id = ic.user_id AND ucc.type_id = ic.type_id 
        AND ucc.card_id = ic.card_id AND ucc.variant_key = ic.variant_key
    WHERE COALESCE(ucc.quantity, 0) < ic.needed_quantity
    """
        
    result = await db.execute(text(final_sql))
    deficit_cards = result.fetchall()
        
    if(len(deficit_cards) > 0):
        return deficit_cards
    
    spend_sql = f"""
            WITH input_cards(user_id, type_id, card_id, variant_key, spend_quantity) AS (
                VALUES {values_clause}
            )
            UPDATE user_card_collection 
            SET quantity = GREATEST(user_card_collection.quantity - ic.spend_quantity, 0)
            FROM input_cards ic
            WHERE user_card_collection.user_id = ic.user_id 
              AND user_card_collection.type_id = ic.type_id
              AND user_card_collection.card_id = ic.card_id 
              AND user_card_collection.variant_key = ic.variant_key
            """
            
    await db.execute(text(spend_sql))

    return []


async def add_cards_to_user(db: AsyncSession, user_id: int, cards: List[UserCardItem]):
    if not cards:
        return
    
    values_list = []
    
    for i, card in enumerate(cards):
        variant_key_param = card.variant_key if isinstance(card.variant_key, dict) else json.loads(card.variant_key)
        
        values_list.append(f"({user_id}::bigint, {card.type_id}::int, {card.card_id}::int, '{json.dumps(variant_key_param)}'::jsonb, {card.quantity}::int)")
    
    values_clause = ", ".join(values_list)
    
    query = f"""
        INSERT INTO user_card_collection (user_id, type_id, card_id, variant_key, quantity)
        VALUES {values_clause}
        ON CONFLICT (user_id, type_id, card_id, variant_key) 
        DO UPDATE SET quantity = user_card_collection.quantity + EXCLUDED.quantity
    """
    
    await db.execute(text(query))

async def craft_card(request: CraftRequest, db: AsyncSession):
    """
    Card crafting function.
    """
    user_id = request.user_id
    ingredients = request.ingredients
    new_category = request.new_category
    
    
    # Validate ingredient types
    invalid_types = [ing for ing in ingredients if ing.type_id != 1]
    if invalid_types:
        return ApiResponse[dict](
            success=False, 
            data={"reason": "only_playable_cards_allowed", "invalid_types": [t.type_id for t in invalid_types]}
        )
    
    # Validate all ingredients belong to the same category and check against crafting rules
    card_ids = [ing.card_id for ing in ingredients]
    
    # Get crafting rule
    rules_result = await db.execute(text("""
        SELECT required_count, from_category 
        FROM craft_rules 
        WHERE category = :new_category
    """), {"new_category": new_category})
    
    rule = rules_result.fetchone()
    if not rule:
        raise HTTPException(400, "Crafting rules not found")
    
    required_count, from_category = rule
    
    # Check ingredient categories in bulk
    cards_result = await db.execute(text("""
        SELECT COUNT(DISTINCT category), MIN(category)
        FROM playable_card_definitions 
        WHERE card_id = ANY(:card_ids)
    """), {"card_ids": card_ids})
    
    count_distinct, min_category = cards_result.fetchone()
    
    if count_distinct != 1 or min_category != from_category:
        return ApiResponse[dict](success=False, data={"reason": "ingredients_category_mismatch"})
        
    total_quantity = sum(ing.quantity for ing in ingredients)
    chance = min(total_quantity / required_count, 1.0)  # Cap at 100%
    craft_success = random.random() < chance
        
    data = {"craft_success": craft_success}
    if craft_success:
        result = await db.execute(text("""
            SELECT * FROM playable_card_definitions 
            WHERE active = TRUE AND category = :new_category 
            ORDER BY RANDOM() LIMIT 1
        """), {"new_category": new_category})
        
        new_card = result.fetchone()
        if new_card:
            card_data = dict(new_card._mapping)
            new_card_item = PlayableCard(
                **card_data,
                variant_key={'level': 1},
                quantity=1
            )
            
            await add_cards_to_user(db, user_id, [new_card_item])
    
    missing_cards = await spend_user_cards(db, user_id, ingredients)
    if(len(missing_cards) > 0):
        raise HTTPException(status_code=500, detail="Missing Cards")
    
    logger.info(f"Craft {craft_success} for user {user_id}")
    
    return ApiResponse[PlayableCard](success=True, data=new_card_item)

async def get_card_info(card: UserCardItem, db: AsyncSession):
    try:
        stmt = select(
            PlayableCardDefinitions.card_id,
            PlayableCardDefinitions.png_name,
            PlayableCardDefinitions.category,
        ).where(
            PlayableCardDefinitions.card_id == card.card_id,
        )

        result = await db.execute(stmt)
        row = result.fetchone()
        return PlayableCard(**row)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# API ENDPOINTS
@router.post("/get_cards_with_selected", response_model=ApiResponse)
async def get_cards_with_selected(request: CollectionWithSelectionRequest, db: AsyncSession = Depends(get_db)):
    return await get_user_playable_cards(user_id=request.user_id, db=db)

@router.post("/craft_card", response_model=ApiResponse)
async def craft_card_endpoint(request: CraftRequest, db: AsyncSession = Depends(get_db)):
    """Optimized card crafting endpoint."""
    try:
        return await craft_card(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Craft failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Craft error")

@router.get("/get_collection/{user_id}", response_model=ApiResponse)
async def get_user_collection(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    # Async JOIN запрос
    stmt = select(
        UserCardCollection.type_id,
        UserCardCollection.card_id,
        UserCardCollection.quantity,
        UserCardCollection.variant_key
    ).where(
        and_(
            UserCardCollection.user_id == user_id,
            UserCardCollection.quantity > 0
        )
    )
    
    result = await db.execute(stmt)
    rows = result.fetchall()
    
    cards = []
    for row in rows:
        # Правильно извлекаем значения из Row
        cards.append(UserCardItem(
            type_id=row.type_id,
            card_id=row.card_id,
            quantity=row.quantity,
            variant_key=row.variant_key  # строка или dict
        ))
    
    logger.info(f"Found {len(cards)} cards for user {user_id}")
    return ApiResponse[List[UserCardItem]](success=True, data=cards)


@router.get("/playable/{user_id}", response_model=ApiResponse)
async def get_user_playable_cards(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    # Async JOIN запрос
    stmt = select(
        UserCardCollection.card_id,
        UserCardCollection.quantity,
        UserCardCollection.variant_key
    ).join(
        PlayableCardDefinitions,
        and_(
            UserCardCollection.type_id == PlayableCardDefinitions.type_id,
            UserCardCollection.card_id == PlayableCardDefinitions.card_id
        )
    ).where(
        and_(
            UserCardCollection.user_id == user_id,
            UserCardCollection.type_id == 1,
            UserCardCollection.quantity > 0
        )
    )
    
    result = await db.execute(stmt)
    rows = result.fetchall()
    
    cards = []
    for row in rows:
        cards.append(PlayableCard(
            card_id=row[0],
            quantity=row[1],
            variant_key=row[2]
        ))
        
    logger.info(cards)
    return ApiResponse[List[PlayableCard]](success=True, data=cards)


@router.get("/exclusive/{user_id}", response_model=ApiResponse)
async def get_user_exclusive_cards(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Async JOIN запрос
        stmt = select(
            UserCardCollection.card_id,
            UserCardCollection.quantity,
            UserCardCollection.variant_key
        ).join(
            ExclusiveCardDefinitions,
            and_(
                UserCardCollection.type_id == ExclusiveCardDefinitions.type_id,
                UserCardCollection.card_id == ExclusiveCardDefinitions.card_id
            )
        ).where(
            and_(
                UserCardCollection.user_id == user_id,
                UserCardCollection.type_id == 2,
                UserCardCollection.quantity > 0
            )
        )
        
        result = await db.execute(stmt)
        rows = result.fetchall()
        
        cards = []
        for row in rows:
            cards.append(ExclusiveCard(
                card_id=row[0],
                quantity=row[1],
                variant_key=row[2]
            ))
            
        return ApiResponse[List[ExclusiveCard]](success=True, data=cards)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clip/{user_id}", response_model=ApiResponse)
async def get_user_clip_cards(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Async JOIN запрос
        stmt = select(
            UserCardCollection.card_id,
            UserCardCollection.quantity,
            UserCardCollection.variant_key
        ).join(
            ClipCardDefinitions,
            and_(
                UserCardCollection.type_id == ClipCardDefinitions.type_id,
                UserCardCollection.card_id == ClipCardDefinitions.card_id
            )
        ).where(
            and_(
                UserCardCollection.user_id == user_id,
                UserCardCollection.type_id == 3,
                UserCardCollection.quantity > 0
            )
        )
        
        result = await db.execute(stmt)
        rows = result.fetchall()
        
        cards = []
        for row in rows:
            cards.append(ClipCard(
                card_id=row[0],
                quantity=row[1],
                variant_key=row[2]
            ))
            
        return ApiResponse[List[ClipCard]](success=True, data=cards)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cards_static_info", response_model=ApiResponse)
async def get_cards_static_info(db: AsyncSession = Depends(get_db)):

    # Playable cards
    result = await db.execute(select(PlayableCardDefinitions))
    playable = result.scalars().all()
    playable_data = [{"type_id": 1, **model_to_dict(card)} for card in playable]
    
    # Exclusive cards
    result = await db.execute(select(ExclusiveCardDefinitions))
    exclusive = result.scalars().all()
    exclusive_data = [{"type_id": 2, **model_to_dict(card)} for card in exclusive]
    
    # Clip cards
    result = await db.execute(select(ClipCardDefinitions))
    clip = result.scalars().all()
    clip_data = [{"type_id": 3, **model_to_dict(card)} for card in clip]

    all_cards = playable_data + exclusive_data + clip_data
    
    logger.info(f"Total cards: {len(playable_data) + len(exclusive_data) + len(clip_data)}")
    return ApiResponse(success=True, data=all_cards)

__all__ = ["router"]