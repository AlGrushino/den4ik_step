from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger, DateTime, ForeignKey, CheckConstraint, Index, Boolean, Date

from sqlalchemy.dialects.postgresql import JSONB

from sqlalchemy.orm import relationship
from database import Base

class CardTypes(Base):
    __tablename__ = "card_types"
    type_id = Column(Integer, primary_key=True)
    type_name = Column(String(50))

class PlayableCardDefinitions(Base):
    __tablename__ = "playable_card_definitions"
    type_id = Column(Integer, primary_key=True, default=1)
    card_id = Column(Integer, primary_key=True)

    player_name      = Column(String(100))
    pos              = Column(String(10))
    club             = Column(String(50)) 
    png_name         = Column(String(50))
    category         = Column(String(20))
    mid_range_shot   = Column(Integer  , default = 0)
    threepoint_shot  = Column(Integer  , default = 0)
    layup            = Column(Integer  , default = 0)
    dunk             = Column(Integer  , default = 0)
    perimetr_defense = Column(Integer  , default = 0)
    interior_defense = Column(Integer  , default = 0)
    dribbling        = Column(Integer  , default = 0)
    passplay         = Column(Integer  , default = 0)
    hands            = Column(Integer  , default = 0)
    steal            = Column(Integer  , default = 0)
    pass_perception  = Column(Integer  , default = 0)
    block            = Column(Integer  , default = 0)
    active           = Column(Boolean  , default = True)

class ExclusiveCardDefinitions(Base):
    __tablename__ = "exclusive_card_definitions"
    type_id = Column(Integer, primary_key=True, default=2)
    card_id = Column(Integer, primary_key=True)
    png_name = Column(String(50))
    collection_name = Column(String(50))
    card_name = Column(String(50))

class ClipCardDefinitions(Base):
    __tablename__ = "clip_card_definitions"
    type_id = Column(Integer, primary_key=True, default=3)
    card_id = Column(Integer, primary_key=True)
    png_name = Column(String(50))
    description = Column(String(200))

class UserCardCollection(Base):
    __tablename__ = "user_card_collection"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger)
    type_id = Column(Integer)
    card_id = Column(Integer)
    variant_key = Column(JSONB)
    quantity = Column(Integer, default=1)

class Trade(Base):
    __tablename__ = "trades"
    trade_id = Column(Integer, primary_key=True)
    from_id = Column(BigInteger)
    to_id = Column(BigInteger)

    items = relationship("TradeItem", back_populates="trade", cascade="all, delete-orphan")
    
class TradeItem(Base):
    __tablename__ = "trade_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(Integer, ForeignKey("trades.trade_id", ondelete="CASCADE"), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # 'from'/'to'
    type_id = Column(Integer, nullable=False, index=True)
    card_id = Column(Integer, nullable=False, index=True)
    
    variant_key = Column(JSONB, nullable=True)  # str или dict → JSONB auto
    quantity = Column(Integer, nullable=False)
    
    # Связи (опционально, для удобства)
    trade = relationship("Trade", back_populates="items")
    
    __table_args__ = (
        # ✅ Check constraints ТУТ
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
        CheckConstraint("side IN ('from', 'to')", name='check_side_valid'),
        
        # ✅ Индексы ТУТ
        Index('idx_trade_items_trade_side', 'trade_id', 'side'),
        Index('idx_trade_items_type_card', 'type_id', 'card_id'),
    )

class ArchiveItem(Base):
    __tablename__ = "archive_item"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    type_id = Column(Integer)
    card_id = Column(Integer)

class UserAlbum(Base):
    __tablename__ = "user_albums"
    
    album_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    name = Column(String(255))
    capacity = Column(Integer)

class AlbumCard(Base):
    __tablename__ = "album_cards"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    album_id = Column(Integer)
    type_id = Column(Integer)
    card_id = Column(Integer)
    variant_key = Column(JSONB)
    position = Column(Integer)


class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String)

class UserCurrency(Base):
    __tablename__ = "user_currency"
    user_id = Column(BigInteger, primary_key=True)
    game_currency = Column(Integer)
    premium_currency = Column(Integer)

class PriceItem(Base):
    __tablename__ = "items_price"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50))
    target_id = Column(Integer, default = 0)
    game_price = Column(Integer, default = 0)
    premium_price = Column(Integer, default = 0)
    is_active = Column(Boolean, default = True)

class DailyStore(Base):
    __tablename__ = "daily_store"
    
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, nullable=False)
    type_id = Column(Integer, nullable=False)
    game_currency = Column(Integer, nullable=False)
    
    purchases = relationship("UserDailyPurchase", back_populates="store_card")

class UserDailyPurchase(Base):
    __tablename__ = "user_daily_purchases"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    buy_id = Column(Integer, ForeignKey("daily_store.id"), nullable=False)
    purchase_date = Column(Date, default="CURRENT_DATE")
    
    store_card = relationship("DailyStore", back_populates="purchases")


def model_to_dict(model):
    if model is None:
        return {}
    return {c.name: getattr(model, c.name) for c in model.__table__.columns}
