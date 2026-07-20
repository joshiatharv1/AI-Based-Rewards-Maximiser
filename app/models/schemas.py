from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class CardStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"


class PaymentType(str, Enum):
    POINTS_ONLY = "points_only"
    CASH_ONLY = "cash_only"
    SPLIT = "split"


# ─── Credit Card Models ───────────────────────────────────────────────────────

class CreditCard(BaseModel):
    card_id: str
    card_name: str
    issuer: str                         # e.g. "Chase", "American Express"
    card_key: str                       # RewardsCC card key e.g. "chase-sapphire-preferred"
    last_four: str
    points_balance: int
    points_currency: str               # e.g. "Chase Ultimate Rewards"
    status: CardStatus = CardStatus.VALID
    valid_denominations: List[int] = [1000, 5000, 10000, 25000, 50000]


class UserCards(BaseModel):
    user_id: str
    cards: List[CreditCard]


# ─── Hotel Models ─────────────────────────────────────────────────────────────

class HotelSearchRequest(BaseModel):
    city_code: str = Field(..., example="NYC")
    check_in: str  = Field(..., example="2025-09-01")
    check_out: str = Field(..., example="2025-09-03")
    adults: int    = Field(default=1, ge=1, le=9)


class HotelOffer(BaseModel):
    hotel_id: str
    hotel_name: str
    chain_code: str                    # e.g. "MC" = Marriott, "HH" = Hilton
    loyalty_program: str               # e.g. "Marriott Bonvoy"
    room_rate_per_night: float
    total_nights: int
    room_subtotal: float
    taxes: float
    resort_fees: float
    total_price: float
    currency: str = "USD"


# ─── Conversion Models ────────────────────────────────────────────────────────

class TransferPartner(BaseModel):
    partner_name: str                  # e.g. "Marriott Bonvoy"
    partner_program_key: str           # e.g. "marriott-bonvoy"
    transfer_ratio: float              # e.g. 0.7 means 1000 card pts = 700 hotel pts
    min_transfer: int                  # minimum points to transfer
    transfer_increments: List[int]     # valid denominations for this partner


class ConversionRequest(BaseModel):
    card_id: str
    card_key: str                      # RewardsCC key
    hotel_loyalty_program: str         # which program to convert into
    points_to_use: int                 # must be a valid denomination


class ConversionResult(BaseModel):
    card_id: str
    card_key: str
    points_used: int
    transfer_ratio: float
    hotel_points_received: int
    hotel_program: str
    points_dollar_value: float         # how much the points are worth in USD
    remaining_card_points: int


# ─── Booking Models ───────────────────────────────────────────────────────────

class BookingPreviewRequest(BaseModel):
    user_id: str
    card_id: str
    hotel_offer_id: str
    hotel_offer: HotelOffer
    points_to_use: int
    loyalty_program: str
    conversion_result: ConversionResult


class PaymentBreakdown(BaseModel):
    room_subtotal: float
    taxes: float
    resort_fees: float
    total_before_points: float
    points_used: int
    points_dollar_value: float
    cash_remainder: float
    payment_type: PaymentType
    currency: str = "USD"


class BookingPreviewResponse(BaseModel):
    hotel_name: str
    check_in: str
    check_out: str
    loyalty_program: str
    transfer_ratio: float
    points_used: int
    hotel_points_received: int
    breakdown: PaymentBreakdown
    ready_to_confirm: bool = True


class BookingConfirmRequest(BaseModel):
    user_id: str
    card_id: str
    hotel_offer_id: str
    points_to_use: int
    loyalty_program: str


class BookingConfirmResponse(BaseModel):
    booking_id: str
    status: str
    hotel_name: str
    confirmation_number: str
    breakdown: PaymentBreakdown


# ─── Agent Models ─────────────────────────────────────────────────────────────

class AgentRecommendation(BaseModel):
    rank: int
    card_id: str
    card_name: str
    loyalty_program: str
    points_to_use: int
    hotel_points_received: int
    transfer_ratio: float
    cash_remainder: float
    value_per_point: float             # cents per point
    reasoning: str                     # plain English explanation


class AgentResponse(BaseModel):
    hotel_name: str
    top_recommendations: List[AgentRecommendation]
    agent_summary: str
    _debug: dict = {}   # exposes valid_cards, hotels, all_options for frontend animation