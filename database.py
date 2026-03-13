from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os


DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_HOST = 'postgres'
DB_PORT = 5432
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db() -> AsyncSession:
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except:
        await session.rollback()
    finally:
        await session.close()