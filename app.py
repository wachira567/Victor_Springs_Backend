from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List  # <--- CHANGED: Added this import
from models import get_db, Property, UnitType, User, Appointment, VacancyAlert, UserRole
import schemas
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets

app = FastAPI(title="Victor Springs API")

# Temporary token storage for Google OAuth
google_tokens = {}

# Load environment variables
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY set in .env file")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Allow Frontend to talk to Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173"],  # Allow specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Get current user from JWT token"""
    try:
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# --- AUTH ENDPOINTS ---


@app.get("/login/google")
def login_google():
    """Redirect to Google OAuth"""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"response_type=code&"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri=http://127.0.0.1:8000/auth/google/callback&"
        f"scope=openid email profile&"
        f"state=google"
    )
    from fastapi.responses import RedirectResponse

    return RedirectResponse(google_auth_url)


@app.get("/auth/google/callback")
def auth_google_callback(code: str, state: str = None, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    from fastapi.responses import RedirectResponse

    try:
        # Exchange code for token
        import requests

        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": "http://127.0.0.1:8000/auth/google/callback",
        }
        token_response = requests.post(token_url, data=data)
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data["access_token"]

        # Get user info
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = requests.get(user_info_url, headers=headers)
        user_response.raise_for_status()
        user_info = user_response.json()

        email = user_info["email"]
        first_name = user_info.get("given_name", "")
        last_name = user_info.get("family_name", "")

        # Check if user exists
        user = db.query(User).filter(User.email == email).first()

        if not user:
            # Create new user
            user = User(
                email=email,
                phone_number="",  # Google users don't have phone
                first_name=first_name,
                last_name=last_name,
                role=UserRole.tenant,  # Google users are tenants
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Create JWT token
        jwt_token = create_access_token(
            data={"sub": str(user.id), "role": user.role.value}
        )

        # Store token data with a short code
        code = secrets.token_urlsafe(16)
        google_tokens[code] = {
            "access_token": jwt_token,
            "role": user.role.value,
            "user_id": user.id,
        }

        # Redirect to frontend with code
        redirect_url = f"{FRONTEND_URL}/google-callback?code={code}"
        return RedirectResponse(redirect_url)

    except Exception as e:
        # On error, redirect to login
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_auth_failed")


@app.get("/auth/google/token")
def get_google_token(code: str):
    """Get Google OAuth token data by code"""
    if code in google_tokens:
        token_data = google_tokens.pop(code)  # Remove after use
        return token_data
    else:
        raise HTTPException(status_code=404, detail="Code not found or expired")


@app.get("/users/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role.value,
    }


@app.post("/token")
def login(form_data: dict, db: Session = Depends(get_db)):
    """OAuth2 compatible token login"""
    username = form_data.get("username")
    password = form_data.get("password")

    # For now, since no password field, just check if user exists
    # In real app, you'd hash and check password
    user = db.query(User).filter(User.email == username).first()

    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "role": user.role.value,
    }


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
