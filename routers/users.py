from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, and_
from typing import List
from database import get_db
from models import User
from schemas import ApiResponse, UserSearchResult
from logger import logger

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/find_user/{username}", response_model=ApiResponse)
async def find_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    limit: int = 5
):
    safe_username = username.replace('%', '\\%').replace('_', '\\_')
    
    query = text("""
        SELECT user_id, username,
               POSITION(LOWER(:subname) IN LOWER(username)) as pos,
               CASE 
                   WHEN username ILIKE :start_pattern THEN 1
                   WHEN username ILIKE :end_pattern THEN 2
                   ELSE 3
               END as match_type
        FROM users 
        WHERE username ILIKE :search_pattern
        ORDER BY 
            match_type,
            pos,
            LENGTH(username)
        LIMIT 5;
    """)
    
    result = await db.execute(query, {
        "subname": safe_username,
        "search_pattern": f"%{safe_username}%",
        "start_pattern": f"{safe_username}%", 
        "end_pattern": f"%{safe_username}"
    })
    
    rows = result.fetchall()
    
    # ✅ Правильный доступ к полям Row (НЕ user.user_id!)
    users = []
    for row in rows:
        users.append({
            "user_id": row[0],      # user_id
            "username": row[1]      # username
        })
    logger.info(f"✅ Found {len(users)} users")
        
    return ApiResponse[List[UserSearchResult]](success=True, data=users, count=len(users))