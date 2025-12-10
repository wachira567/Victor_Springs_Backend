from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List  # <--- CHANGED: Added this import
from models import get_db, Property, UnitType, User, Appointment, VacancyAlert, UserRole
import schemas
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os

app = FastAPI(title="Victor Springs API")

# Allow Frontend to talk to Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Temporarily allow all origins for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GET REQUESTS (Reading Data) ---


# CHANGED: Used List[...] instead of list[...]
@app.get("/properties", response_model=List[schemas.PropertyBase])
def get_properties(db: Session = Depends(get_db)):
    """
    Fetch all properties with their units and images nested inside.
    """
    properties = db.query(Property).all()
    return properties


@app.get("/properties/{property_id}", response_model=schemas.PropertyBase)
def get_property_detail(property_id: int, db: Session = Depends(get_db)):
    """
    Fetch specific property details.
    """
    property = db.query(Property).filter(Property.id == property_id).first()
    if not property:
        raise HTTPException(status_code=404, detail="Property not found")
    return property


@app.get("/properties/{property_id}/booked-dates")
def get_property_booked_dates(property_id: int, db: Session = Depends(get_db)):
    """
    Get booked dates for a specific property.
    For now, return empty list as we don't have booking dates in the current schema.
    """
    # Check if property exists
    property = db.query(Property).filter(Property.id == property_id).first()
    if not property:
        raise HTTPException(status_code=404, detail="Property not found")

    # For now, return empty list since we don't have booking dates in the current schema
    # In the future, this would query appointments for this property
    return {"booked_dates": []}


# --- POST REQUESTS (Creating Data) ---


@app.post("/book-viewing", status_code=status.HTTP_201_CREATED)
def book_viewing(booking: schemas.BookingRequest, db: Session = Depends(get_db)):
    """
    Smart Booking System:
    1. Checks if user exists by email.
    2. If not, creates a new 'Guest' user.
    3. Creates the appointment.
    """

    # 1. Check/Create User
    user = db.query(User).filter(User.email == booking.email).first()

    if not user:
        # Create new Guest
        user = User(
            email=booking.email,
            phone_number=booking.phone_number,
            first_name=booking.first_name,
            last_name=booking.last_name,
            role=UserRole.guest,
        )
        db.add(user)
        db.commit()
        db.refresh(user)  # Get the new ID

    # 2. Check if Unit Type exists
    unit_type = db.query(UnitType).filter(UnitType.id == booking.unit_type_id).first()
    if not unit_type:
        raise HTTPException(status_code=404, detail="Unit type not found")

    # 3. Create Appointment
    new_appointment = Appointment(
        user_id=user.id,
        unit_type_id=booking.unit_type_id,
        appointment_date=booking.appointment_date,
        admin_notes=f"Message from user: {booking.message}" if booking.message else "",
    )

    db.add(new_appointment)
    db.commit()

    return {
        "message": "Appointment booked successfully",
        "appointment_id": new_appointment.id,
    }


@app.post("/join-waitlist", status_code=status.HTTP_201_CREATED)
def join_waitlist(request: schemas.WaitlistRequest, db: Session = Depends(get_db)):
    # 1. Check/Create User (Reusable logic)
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        user = User(
            email=request.email,
            phone_number=request.phone_number,
            first_name=request.first_name,
            role=UserRole.guest,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 2. Add to Waitlist
    alert = VacancyAlert(
        user_id=user.id,
        unit_type_id=request.unit_type_id,
        valid_until=request.valid_until,
    )

    db.add(alert)
    db.commit()

    return {"message": "Added to waitlist successfully"}
