from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import cards, users, trades, albums, currency, prices
import asyncio
from database import engine, Base
import logging
from logger import logger

from fastapi.staticfiles import StaticFiles
from pathlib import Path

from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).parent
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)



# Создание таблиц
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app = FastAPI(title="StepApp API", version="1.0.0", debug=True)

app.mount("/api/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
    
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Ошибка в {request.url}: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={"success": False, "detail": "Внутренняя ошибка сервера"}
    )

# CORS для Unity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards.router)
app.include_router(users.router)
app.include_router(trades.router)
app.include_router(albums.router)
app.include_router(currency.router)
app.include_router(prices.router)

@app.on_event("startup")
async def startup():
    await init_db()
    print("🚀 Database initialized!")

@app.get("/")
async def root():
    return {"message": "CardGame API is running!", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)