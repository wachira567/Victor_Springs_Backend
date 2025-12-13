import os
from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    Date,
    ForeignKey,
    Numeric,
    Enum,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import enum

# --- 1. SECURE CONNECTION ---
load_dotenv()  # Load variables from .env
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("No DATABASE_URL set in .env file")

engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,  # Check connection before using
    pool_recycle=300,  # Recycle connections every 5 minutes
    pool_size=10,  # Maximum connections in pool
    max_overflow=20,  # Allow overflow connections
    connect_args={
        "connect_timeout": 10,
        # Removed statement_timeout for Neon compatibility
    },
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Helper function to handle database reconnections
def get_db_with_retry(max_retries=3):
    """Get database session with automatic retry on connection failures"""
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            # Test the connection
            db.execute("SELECT 1")
            return db
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Database connection attempt {attempt + 1} failed, retrying...")
            import time

            time.sleep(1)  # Wait 1 second before retry


# --- 2. ENUMS ---
class UserRole(enum.Enum):
    guest = "guest"
    tenant = "tenant"
    admin = "admin"


class UnitCategory(enum.Enum):
    bedsitter = "bedsitter"
    single_room = "single_room"
    one_bedroom = "one_bedroom"
    two_bedroom = "two_bedroom"
    three_bedroom = "three_bedroom"
    four_bedroom_plus = "four_bedroom_plus"


class AppointmentStatus(enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class BookingIntent(enum.Enum):
    viewing = "viewing"
    waitlist_join = "waitlist_join"


class DocType(enum.Enum):
    agreement = "agreement"
    rules = "rules"
    fee_structure = "fee_structure"


# --- 3. TABLES ---


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    phone_number = Column(String, nullable=True)
    first_name = Column(String)
    last_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.guest)
    created_at = Column(DateTime, default=datetime.now)


class Property(Base):
    __tablename__ = "properties"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True)
    address = Column(Text)
    city = Column(String)
    neighborhood = Column(String)

    has_parking = Column(Boolean, default=False)
    has_security = Column(Boolean, default=False)
    has_borehole = Column(Boolean, default=False)

    primary_image_url = Column(String)
    description = Column(Text)

    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))

    created_at = Column(DateTime, default=datetime.now)

    unit_types = relationship("UnitType", back_populates="property")


class UnitType(Base):
    __tablename__ = "unit_types"
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"))

    name = Column(String)
    category = Column(Enum(UnitCategory))

    price_per_month = Column(Numeric(10, 2))
    deposit_amount = Column(Numeric(10, 2))
    agreement_fee = Column(Numeric(10, 2), default=0)
    garbage_fee_monthly = Column(Numeric(10, 2), default=0)
    water_fee_monthly = Column(Numeric(10, 2), default=0)
    internet_fee_monthly = Column(Numeric(10, 2), default=0)
    other_fees = Column(Numeric(10, 2), default=0)

    total_units_count = Column(Integer)
    available_units_count = Column(Integer)

    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    property = relationship("Property", back_populates="unit_types")
    images = relationship("UnitImage", back_populates="unit_type")


class UnitImage(Base):
    __tablename__ = "unit_images"
    id = Column(Integer, primary_key=True)
    unit_type_id = Column(Integer, ForeignKey("unit_types.id"))
    cloudinary_public_id = Column(String)
    image_url = Column(String)
    caption = Column(String)
    is_primary = Column(Boolean, default=False)

    unit_type = relationship("UnitType", back_populates="images")


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # Allow null for guests
    guest_id = Column(String, nullable=True)  # Random ID for guest tracking
    unit_type_id = Column(Integer, ForeignKey("unit_types.id"))

    appointment_date = Column(DateTime)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.pending)
    type = Column(Enum(BookingIntent), default=BookingIntent.viewing)

    admin_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    user = relationship("User")
    unit_type = relationship("UnitType")


class VacancyAlert(Base):
    __tablename__ = "vacancy_alerts"
    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # Allow null for guests
    guest_id = Column(String, nullable=True)  # Random ID for guest tracking
    unit_type_id = Column(Integer, ForeignKey("unit_types.id"))
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    special_requests = Column(Text, nullable=True)
    valid_until = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    unit_type = relationship("UnitType")


class SavedProperty(Base):
    __tablename__ = "saved_properties"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    property_id = Column(Integer, ForeignKey("properties.id"))
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User")
    property = relationship("Property")


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    unit_type_id = Column(Integer, ForeignKey("unit_types.id"), nullable=True)
    title = Column(String)
    file_url = Column(String)
    doc_type = Column(Enum(DocType))


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id = Column(Integer, primary_key=True)
    vacancy_alert_id = Column(Integer, ForeignKey("vacancy_alerts.id"))
    message_type = Column(String)  # 'unit_available', 'custom', etc.
    message_content = Column(Text)
    recipient_phone = Column(String)
    delivery_method = Column(String)  # 'whatsapp', 'sms', 'failed'
    sent_at = Column(DateTime, default=datetime.now)
    success = Column(Boolean, default=True)

    # Relationships
    vacancy_alert = relationship("VacancyAlert")
