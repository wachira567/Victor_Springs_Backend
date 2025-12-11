from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, date
from models import UnitCategory, BookingIntent, AppointmentStatus

# --- 1. SHARED PIECES ---


class UnitImageBase(BaseModel):
    image_url: str
    caption: Optional[str] = None
    is_primary: bool = False

    class Config:
        from_attributes = True


class UnitTypeBase(BaseModel):
    id: int
    name: Optional[str] = None
    category: Optional[UnitCategory] = None
    price_per_month: Optional[float] = None
    deposit_amount: Optional[float] = None
    agreement_fee: Optional[float] = None
    garbage_fee_monthly: Optional[float] = None
    water_fee_monthly: Optional[float] = None
    internet_fee_monthly: Optional[float] = None
    other_fees: Optional[float] = None
    total_units_count: Optional[int] = None
    available_units_count: Optional[int] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    images: List[UnitImageBase] = []  # Nested images

    class Config:
        from_attributes = True


class PropertyBase(BaseModel):
    id: int
    name: Optional[str] = None
    slug: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    has_parking: bool = False
    has_security: bool = False
    has_borehole: bool = False
    created_at: Optional[datetime] = None
    unit_types: List[UnitTypeBase] = []  # Nested units

    class Config:
        from_attributes = True


class AppointmentBase(BaseModel):
    id: int
    user_id: int
    unit_type_id: int
    appointment_date: datetime
    status: AppointmentStatus
    type: BookingIntent
    admin_notes: Optional[str] = None
    created_at: datetime
    unit_type: UnitTypeBase

    class Config:
        from_attributes = True


# --- 2. INPUT SCHEMAS (Data coming FROM React) ---


# When a user books, they send this:
class BookingRequest(BaseModel):
    # User Details
    first_name: str
    last_name: str
    email: EmailStr
    phone_number: str

    # Booking Details
    unit_type_id: int
    appointment_date: datetime
    message: Optional[str] = None


# When a user joins waitlist:
class WaitlistRequest(BaseModel):
    first_name: str
    email: EmailStr
    phone_number: str
    unit_type_id: int
    valid_until: date  # "Keep me on list until..."
