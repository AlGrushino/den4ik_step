from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List
from database import get_db
from models import ArchiveItem, UserAlbum, AlbumCard
from schemas import CardKey, ApiResponse

from schemas import AddToCustomAlbumRequest, BuyAlbumRequest, RemoveFromCustomAlbumRequest, UserCardItem

from logger import logger
import random, json

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text

from sqlalchemy import select

from routers import cards

router = APIRouter(prefix="/api/albums", tags=["albums"])

@router.get("/archive/{user_id}", response_model=ApiResponse)
async def get_user_archive_cards(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(
            ArchiveItem.type_id,
            ArchiveItem.card_id
        ).where(
            ArchiveItem.user_id == user_id,
        )


    result = await db.execute(stmt)
    rows = result.fetchall()
    
    cards = []
    for row in rows:
        cards.append(CardKey(
            type_id=row[0],
            card_id=row[1],
        ))
        
    return ApiResponse[List[CardKey]](success=True, data=cards)

async def add_album_page(db: AsyncSession, user_id : int, album_id : int):
    album_stmt = select(UserAlbum).where(
        and_(UserAlbum.user_id == user_id, UserAlbum.album_id == album_id)
    )
    result = await db.execute(album_stmt)
    album = result.scalars().first()

    if album is None:
        logger.error(f"Нет альбома {album_id} у юзера {user_id}")
        raise HTTPException(status_code=404, detail="Album not found")

    album.capacity += 9

    album_data = {
        "album_id": album.album_id,
        "name": album.name,
        "capacity": album.capacity,
        "cards": [None] * album.capacity,
    }

    return album_data
    
async def create_custom_album(db: AsyncSession, user_id : int):
    count_stmt = (
        select(func.count(UserAlbum.album_id))
        .where(UserAlbum.user_id == user_id)
    )
    count_result = await db.execute(count_stmt)
    album_count = count_result.scalar()
    
    new_album = UserAlbum(
        user_id=user_id,
        capacity=9,
        name=f"Новый альбом {album_count + 1}"
    )
    
    db.add(new_album)
    await db.flush()
    await db.refresh(new_album)

    logger.info(f"Создал альбом {new_album.album_id}")

    album_data = {
        "album_id": new_album.album_id,
        "name": new_album.name,
        "capacity": new_album.capacity,
        "cards": [None] * new_album.capacity,
    }

    return album_data
    
@router.post("/remove_from_custom_album", response_model=ApiResponse)
async def remove_from_custom_album(
    request_info: RemoveFromCustomAlbumRequest,
    db: AsyncSession = Depends(get_db)
):
    album_id = request_info.album_id
    user_id = request_info.user_id
    position = request_info.position

    logger.info(f"Убираем карту с позиции {position} в альбоме {album_id} юзера {user_id}")

    album_stmt = select(UserAlbum).where(
        and_(UserAlbum.user_id == user_id, UserAlbum.album_id == album_id)
    )
    result = await db.execute(album_stmt)
    album = result.scalars().first()

    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    if position >= album.capacity:
        raise HTTPException(status_code=400, detail="Invalid position")

    card_stmt = select(AlbumCard).where(
        and_(
            AlbumCard.album_id == album.album_id,
            AlbumCard.position == position
        )
    )
    result = await db.execute(card_stmt)
    card_to_remove = result.scalars().first()

    if card_to_remove is None:
        logger.warning(f"Нет карточки на позиции {position} в альбоме {album_id}")
        return ApiResponse(success=True, data=True)
    
    user_card_item = UserCardItem(
        type_id=card_to_remove.type_id,
        card_id=card_to_remove.card_id,
        variant_key=card_to_remove.variant_key,
        quantity=1
    )

    await cards.add_cards_to_user(db, user_id, [user_card_item])

    await db.delete(card_to_remove)

    return ApiResponse(success=True, data=True)


@router.post("/add_to_custom_album", response_model=ApiResponse)
async def add_to_custom_album(
    request_info: AddToCustomAlbumRequest,
    db: AsyncSession = Depends(get_db)
):
    album_id = request_info.album_id
    user_id = request_info.user_id
    position = request_info.position
    user_card = request_info.user_card

    logger.info(f"Добавляем карту {user_card} на позицию {position} юзеру {user_id} в альбом {album_id}")

    album_stmt = select(UserAlbum).where(and_(UserAlbum.user_id == user_id, UserAlbum.album_id == album_id))
    result = await db.execute(album_stmt)
    album = result.scalars().first()

    if(album is None):
        logger.error(f"Нет альбома {album_id} у юзера {user_id}:", exc_info=True)
        raise HTTPException(status_code=500, detail="Album error")
    
    if(position >= album.capacity):
        logger.error(f"Нет места у альбома {album_id} у юзера {user_id}:", exc_info=True)
        raise HTTPException(status_code=500, detail="Album error")
    
    if(len(await cards.spend_user_cards(db, user_id, [user_card])) != 0):
        logger.error(f"Нет карточки для добавления в альбом у юзера {user_id}:", exc_info=True)
        raise HTTPException(status_code=500, detail="Album error")
    
    new_card = AlbumCard(
        album_id=album.album_id,
        type_id=user_card.type_id,
        card_id=user_card.card_id,
        variant_key=user_card.variant_key,
        position=position
    )

    db.add(new_card)

    return ApiResponse[bool](success=True, data=True)

@router.get("/custom_albums/{user_id}", response_model=ApiResponse)
async def get_user_albums_info(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    albums_stmt = select(UserAlbum).where(UserAlbum.user_id == user_id).order_by(UserAlbum.album_id)
    result = await db.execute(albums_stmt)
    albums = result.scalars().all()
    
    albums_data = []
    
    for album in albums:
        cards_stmt = (
            select(AlbumCard)
            .where(AlbumCard.album_id == album.album_id)
            .order_by(AlbumCard.position)
        )
        cards_result = await db.execute(cards_stmt)
        cards = cards_result.scalars().all()
        
        album_cards_array  = [None] * album.capacity
        for card in cards:
            album_cards_array[card.position] = {
                "type_id": card.type_id,
                "card_id": card.card_id,
                "variant_key": card.variant_key,
            }
        
        albums_data.append({
                "album_id": album.album_id,
                "name": album.name,
                "capacity": album.capacity,
                "cards": album_cards_array,
        })
    
    return ApiResponse(success=True, data=albums_data)