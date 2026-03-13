from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, TypeVar, Generic, Tuple
from typing import Union  # Для union типов

class CardKey(BaseModel):
    type_id: int
    card_id: int

class UserCardItem(BaseModel):
    type_id: int
    card_id: int
    variant_key: Union[str, dict[str, Any]] = "{}"
    quantity: int

class PlayableCard(UserCardItem):
    type_id: int = 1
    png_name: str
    
    class Config:
        from_attributes = True

class ExclusiveCard(UserCardItem):
    type_id: int = 2
    png_name: str
    
    class Config:
        from_attributes = True

class ClipCard(UserCardItem):
    type_id: int = 3
    png_name: str
    description: str
    
    class Config:
        from_attributes = True

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T = None
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

class UserSearchResult(BaseModel):
    user_id: int
    username: str

class CardOperation(BaseModel):
    user_id: int
    cards: List[UserCardItem]

class CraftIngredients(BaseModel):
    type_id: int = 1  # playable
    card_id: int
    variant_key: str = "{}"
    quantity: int

class CraftRequest(BaseModel):
    user_id: int
    ingredients: List[CraftIngredients]  # UserCardItem для крафта
    new_category: str

class CollectionWithSelectionRequest(BaseModel):
    user_id: int
    selected: List[UserCardItem]

class TradeRequest(BaseModel):
    from_id: int
    to_id: int
    from_cards: List[UserCardItem]
    to_cards: List[UserCardItem]

class AcceptTradeRequest(BaseModel):
    to_id: int
    trade_id: int

class TradeInfo(BaseModel):
    trade_id: int
    from_id: int
    to_id: int
    from_username: str
    to_username: str

class AddToCustomAlbumRequest(BaseModel):
    user_id: int
    album_id: int
    user_card: UserCardItem
    position: int

class RemoveFromCustomAlbumRequest(BaseModel):
    user_id: int
    album_id: int
    position: int

class BuyAlbumRequest(BaseModel):
    user_id: int
    album_id: int

class UserCurrencyInfo(BaseModel):
    game_currency: int
    premium_currency: int

class PurchaseResponce(UserCurrencyInfo):
    result : dict

class DailyShopCard(BaseModel):
    id: int
    card_id: int
    type_id: int
    game_currency: int

class UserDailyPurchases(BaseModel):
    id: int
    buy_id: int

class PriceItemSchema(BaseModel):
    id: int
    code: str
    target_id: int
    game_price: int
    premium_price: int
    is_active: bool

class PurchaseRequest(BaseModel):
    user_id : int
    code : str
    payload : Union[str, dict[str, Any]] = "{}"
    target_id : int

    