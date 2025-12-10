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
    name: str
    category: UnitCategory
    price_per_month: float
    description: Optional[str] = None
    images: List[UnitImageBase] = [] # Nested images

    class Config:
        from_attributes = True

class PropertyBase(BaseModel):
    id: int
    name: str
    address: str
    city: str
    neighborhood: str
    has_parking: bool
    has_security: bool
    unit_types: List[UnitTypeBase] = [] # Nested units

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
    valid_until: date # "Keep me on list until..."