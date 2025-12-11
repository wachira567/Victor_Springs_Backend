from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Header, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional  # <--- CHANGED: Added this import
from models import (
    get_db,
    Property,
    UnitType,
    UnitImage,
    User,
    Appointment,
    VacancyAlert,
    SavedProperty,
    UserRole,
    AppointmentStatus,
    BookingIntent,
)
import schemas
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "notification_service"))
from notification_service import (
    send_booking_confirmation,
    send_booking_reminder,
    send_payment_reminder,
    send_custom_notification,
    send_site_visit_request_notification,
    send_site_visit_confirmation_notification,
    send_express_interest_notification,
    send_unit_available_notification,
    send_site_visit_reminder_notification,
    send_welcome_notification,
    send_account_verification_notification,
    send_password_reset_notification,
)

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

print(f"FRONTEND_URL loaded: {FRONTEND_URL}")

# Allow Frontend to talk to Backend
print("Setting up CORS middleware...")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],  # Allow specific origins
    allow_credentials=True,  # Enable credentials for auth headers
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
print("CORS middleware configured")


# Custom CORS middleware as fallback
@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours for development
REFRESH_TOKEN_EXPIRE_DAYS = 7     # 7 days for user convenience

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Get current user from JWT access token"""
    try:
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )

        # Ensure this is an access token (for new tokens) or allow old tokens without type
        token_type = payload.get("type")
        if token_type is not None and token_type != "access":
            raise HTTPException(
                status_code=401, detail="Invalid token type"
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


def verify_refresh_token(token: str, db: Session = Depends(get_db)):
    """Verify refresh token and return user"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Ensure this is a refresh token (for new tokens) or allow old tokens without type
        token_type = payload.get("type")
        if token_type is not None and token_type != "refresh":
            raise HTTPException(
                status_code=401, detail="Invalid token type"
            )

        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=401, detail="Invalid refresh token"
            )
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(
            status_code=401, detail="Invalid refresh token"
        )


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire.timestamp()), "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": int(expire.timestamp()), "type": "refresh"})
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

        # Create both access and refresh tokens
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role.value}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user.id), "role": user.role.value}
        )

        # Store token data with a short code
        code = secrets.token_urlsafe(16)
        google_tokens[code] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
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
        token_data = google_tokens[code]  # Don't remove after use - allow multiple requests
        return token_data
    else:
        raise HTTPException(status_code=404, detail="Code not found or expired")


@app.post("/auth/refresh")
def refresh_access_token(request: dict, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    try:
        refresh_token = request.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token required")

        # Verify the refresh token
        user = verify_refresh_token(refresh_token, db)

        # Create new access token
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role.value}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.get("/users/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role.value,
        "username": current_user.first_name,  # Using first_name as username for now
        "phone_number": current_user.phone_number,
    }


@app.put("/users/me")
def update_current_user_info(user_data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update current user information"""
    try:
        # Update user fields
        if "first_name" in user_data:
            current_user.first_name = user_data["first_name"]
        if "last_name" in user_data:
            current_user.last_name = user_data["last_name"]
        if "email" in user_data:
            current_user.email = user_data["email"]
        if "phone_number" in user_data:
            current_user.phone_number = user_data["phone_number"]

        db.commit()
        db.refresh(current_user)

        return {
            "id": current_user.id,
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "role": current_user.role.value,
            "username": current_user.first_name,
            "phone_number": current_user.phone_number,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")


@app.delete("/users/me")
def delete_current_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete current user account"""
    try:
        # Delete all related data first to maintain referential integrity

        # Delete saved properties
        db.query(SavedProperty).filter(SavedProperty.user_id == current_user.id).delete()

        # Delete appointments
        db.query(Appointment).filter(Appointment.user_id == current_user.id).delete()

        # Delete vacancy alerts
        db.query(VacancyAlert).filter(VacancyAlert.user_id == current_user.id).delete()

        # Finally delete the user
        db.delete(current_user)
        db.commit()

        return {"message": "Account deleted successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")


@app.post("/token")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """OAuth2 compatible token login with access and refresh tokens"""

    # For now, since no password field, just check if user exists
    # In real app, you'd hash and check password
    user = db.query(User).filter(User.email == username).first()

    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # Create both access and refresh tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "role": user.role.value}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # seconds
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


@app.get("/properties/saved")
def get_saved_properties(Authorization: str = Header(...), db: Session = Depends(get_db)):
    """
    Get all properties saved by the current user.
    Based on VenueVibe's simple and working approach.
    """
    # Extract token from Authorization header
    auth_header = Authorization
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(content={"detail": "Not authenticated"}, status_code=401)

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return JSONResponse(content={"detail": "Invalid token"}, status_code=401)

        # Find user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            return JSONResponse(content={"detail": "User not found"}, status_code=404)

        # Get saved property IDs first
        saved_property_ids = db.query(SavedProperty.property_id).filter(SavedProperty.user_id == user.id).all()
        saved_ids = [item[0] for item in saved_property_ids]

        if not saved_ids:
            return JSONResponse(content=[], status_code=200)

        # Get property details for saved properties with images
        properties = db.query(Property).options(
            selectinload(Property.unit_types).selectinload(UnitType.images)
        ).filter(Property.id.in_(saved_ids)).all()

        result = []
        for property_obj in properties:
            # Get primary image for the property
            primary_image = None
            if property_obj.unit_types:
                for unit_type in property_obj.unit_types:
                    if unit_type.images:
                        primary_img = next((img for img in unit_type.images if img.is_primary), None)
                        if primary_img:
                            primary_image = primary_img.image_url
                            break
                        elif unit_type.images:
                            # If no primary, use first image
                            primary_image = unit_type.images[0].image_url
                            break

            # Convert to plain dict to avoid FastAPI serialization issues
            result.append({
                "id": int(property_obj.id),
                "name": str(property_obj.name or ""),
                "slug": str(property_obj.slug or ""),
                "address": str(property_obj.address or ""),
                "city": str(property_obj.city or ""),
                "neighborhood": str(property_obj.neighborhood or ""),
                "has_parking": bool(property_obj.has_parking),
                "has_security": bool(property_obj.has_security),
                "has_borehole": bool(property_obj.has_borehole),
                "primary_image": primary_image,
            })

        return JSONResponse(content=result, status_code=200)

    except JWTError:
        return JSONResponse(content={"detail": "Invalid token"}, status_code=401)
    except Exception as e:
        print(f"Error fetching saved properties: {e}")
        return JSONResponse(content={"detail": "Internal server error"}, status_code=500)


@app.get("/properties/{property_id}", response_model=schemas.PropertyBase)
def get_property_detail(property_id: int, db: Session = Depends(get_db)):
    """
    Fetch specific property details.
    """
    property = db.query(Property).filter(Property.id == property_id).first()
    if not property:
        raise HTTPException(status_code=404, detail="Property not found")
    return property
    """
    Get all properties saved by the current user.
    Based on VenueVibe's simple and working approach.
    """
    # Extract token from Authorization header
    auth_header = Authorization
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(content={"detail": "Not authenticated"}, status_code=401)

    token = Authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return JSONResponse(content={"detail": "Invalid token"}, status_code=401)

        # Find user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            return JSONResponse(content={"detail": "User not found"}, status_code=404)

        # Get saved property IDs first
        saved_property_ids = db.query(SavedProperty.property_id).filter(SavedProperty.user_id == user.id).all()
        saved_ids = [item[0] for item in saved_property_ids]

        if not saved_ids:
            return JSONResponse(content=[], status_code=200)

        # Get property details for saved properties with images
        properties = db.query(Property).options(
            selectinload(Property.unit_types).selectinload(UnitType.images)
        ).filter(Property.id.in_(saved_ids)).all()

        result = []
        for property_obj in properties:
            # Get primary image for the property
            primary_image = None
            if property_obj.unit_types:
                for unit_type in property_obj.unit_types:
                    if unit_type.images:
                        primary_img = next((img for img in unit_type.images if img.is_primary), None)
                        if primary_img:
                            primary_image = primary_img.image_url
                            break
                        elif unit_type.images:
                            # If no primary, use first image
                            primary_image = unit_type.images[0].image_url
                            break

            # Convert to plain dict to avoid FastAPI serialization issues
            result.append({
                "id": int(property_obj.id),
                "name": str(property_obj.name or ""),
                "slug": str(property_obj.slug or ""),
                "address": str(property_obj.address or ""),
                "city": str(property_obj.city or ""),
                "neighborhood": str(property_obj.neighborhood or ""),
                "has_parking": bool(property_obj.has_parking),
                "has_security": bool(property_obj.has_security),
                "has_borehole": bool(property_obj.has_borehole),
                "primary_image": primary_image,
            })

        return JSONResponse(content=result, status_code=200)

    except JWTError:
        return JSONResponse(content={"detail": "Invalid token"}, status_code=401)
    except Exception as e:
        print(f"Error fetching saved properties: {e}")
        return JSONResponse(content={"detail": "Internal server error"}, status_code=500)


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


@app.get("/bookings/my-bookings")
def get_user_bookings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get bookings for the current user.
    For now, return empty array since booking system is not fully implemented.
    """
    # In a real implementation, you'd query appointments for this user
    # For now, return empty array to prevent 404 errors
    return []


@app.post("/properties/{property_id}/save", status_code=status.HTTP_201_CREATED)
def save_property(property_id: int, Authorization: str = Header(...), db: Session = Depends(get_db)):
    """
    Save a property for the current user.
    Based on VenueVibe's approach with proper HTTP status codes.
    """
    # Extract token from Authorization header
    auth_header = Authorization
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = Authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Find user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if property exists
        property_obj = db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise HTTPException(status_code=404, detail="Property not found")

        # Check if already saved
        existing_save = db.query(SavedProperty).filter(
            SavedProperty.user_id == user.id,
            SavedProperty.property_id == property_id
        ).first()

        if existing_save:
            raise HTTPException(status_code=409, detail="Property already saved")

        # Save the property
        saved_property = SavedProperty(user_id=user.id, property_id=property_id)
        db.add(saved_property)
        db.commit()
        return {"message": "Property saved successfully"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.delete("/properties/{property_id}/save")
def unsave_property(property_id: int, Authorization: str = Header(...), db: Session = Depends(get_db)):
    """
    Remove a property from the user's saved list.
    Based on VenueVibe's approach.
    """
    # Extract token from Authorization header
    auth_header = Authorization
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = Authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Find user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Find and delete the saved property
        saved_property = db.query(SavedProperty).filter(
            SavedProperty.user_id == user.id,
            SavedProperty.property_id == property_id
        ).first()

        if not saved_property:
            raise HTTPException(status_code=404, detail="Property not saved")

        db.delete(saved_property)
        db.commit()
        return {"message": "Property unsaved successfully"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.delete("/user/interests/{interest_id}")
def delete_user_interest(interest_id: int, Authorization: str = Header(...), db: Session = Depends(get_db)):
    """
    Delete a user interest.
    """
    # Extract token from Authorization header
    auth_header = Authorization
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = Authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Find user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Find and delete the interest (only if it belongs to the user)
        interest = db.query(VacancyAlert).filter(
            VacancyAlert.id == interest_id,
            VacancyAlert.user_id == user.id
        ).first()

        if not interest:
            raise HTTPException(status_code=404, detail="Interest not found")

        db.delete(interest)
        db.commit()
        return {"message": "Interest removed successfully"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# --- POST REQUESTS (Creating Data) ---


@app.post("/book-viewing", status_code=status.HTTP_201_CREATED)
def book_viewing(
    booking: schemas.BookingRequest,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """
    Smart Booking System:
    1. Checks if user exists by email.
    2. If not, creates a new 'Guest' user.
    3. Creates the appointment.
    4. Sends confirmation notification via WhatsApp/SMS.
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

    # 4. Send confirmation notification (if background tasks available)
    if background_tasks and booking.phone_number:
        # Get property name from unit type
        property_name = (
            unit_type.property.name if unit_type.property else "Victor Springs Venue"
        )

        booking_data = {
            "venue_name": property_name,
            "event_date": booking.appointment_date.strftime("%Y-%m-%d %H:%M"),
            "total_cost": unit_type.price or 0,
        }

        background_tasks.add_task(
            send_booking_confirmation, booking.phone_number, booking_data
        )

    return {
        "message": "Appointment booked successfully",
        "appointment_id": new_appointment.id,
        "notification_sent": bool(background_tasks and booking.phone_number),
    }


@app.post("/property-interest", status_code=status.HTTP_201_CREATED)
def create_property_interest(request: dict, db: Session = Depends(get_db)):
    """Create property interest for both signed-in users and guests"""
    try:
        user_id = request.get("user_id")
        guest_id = None

        # If no user_id provided, this is a guest
        if not user_id:
            import secrets
            guest_id = secrets.token_urlsafe(8)  # Generate random guest ID

        # Validate required fields
        unit_type_id = request.get("unit_type_id")
        if not unit_type_id:
            raise HTTPException(status_code=400, detail="Unit type ID is required")

        # Check if unit type exists
        unit_type = db.query(UnitType).filter(UnitType.id == unit_type_id).first()
        if not unit_type:
            raise HTTPException(status_code=404, detail="Unit type not found")

        # Create vacancy alert
        alert = VacancyAlert(
            user_id=user_id,
            guest_id=guest_id,
            unit_type_id=unit_type_id,
            contact_name=request.get("contact_name"),
            contact_email=request.get("contact_email"),
            contact_phone=request.get("contact_phone"),
            special_requests=request.get("special_requests"),
            valid_until=datetime.now().date() + timedelta(days=int(request.get("timeframe_months", 3)) * 30),
        )

        db.add(alert)
        db.commit()
        db.refresh(alert)

        # Send notification if phone provided
        if request.get("contact_phone"):
            try:
                property_name = (
                    unit_type.property.name
                    if unit_type and unit_type.property
                    else "Victor Springs Property"
                )

                interest_data = {
                    "contact_name": request.get("contact_name", "Valued Customer"),
                    "property_name": property_name,
                    "timeframe": f"{request.get('timeframe_months', 3)} months",
                    "special_requests": request.get("special_requests", ""),
                }

                send_express_interest_notification(request["contact_phone"], interest_data)
            except Exception as e:
                print(f"Failed to send interest notification: {e}")

        return {
            "message": "Interest recorded successfully",
            "interest_id": alert.id,
            "guest_id": guest_id,
            "notification_sent": bool(request.get("contact_phone")),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to create property interest: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record interest: {str(e)}")


@app.post("/site-visits", status_code=status.HTTP_201_CREATED)
def create_site_visit(
    request: dict,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Create a site visit booking"""
    try:
        # 1. Get or create user
        user_id = request.get("user_id")
        if not user_id:
            # Create guest user if no user_id provided
            user = User(
                email=request.get(
                    "contact_email",
                    f"guest_{request.get('contact_phone')}@victor-springs.com",
                ),
                phone_number=request.get("contact_phone"),
                first_name=request.get("contact_name", "").split()[0]
                if request.get("contact_name")
                else "",
                last_name=" ".join(request.get("contact_name", "").split()[1:])
                if request.get("contact_name")
                and len(request.get("contact_name", "").split()) > 1
                else "",
                role=UserRole.guest,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.id
        else:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

        # 2. Get property information
        property_id = request.get("property_id")
        if not property_id:
            raise HTTPException(status_code=400, detail="Property ID is required")

        property = db.query(Property).filter(Property.id == property_id).first()
        if not property:
            raise HTTPException(status_code=404, detail="Property not found")

        # 3. Create appointment for site visit
        from datetime import datetime

        visit_date_str = request.get("visit_date")
        visit_time_str = request.get("visit_time")

        if visit_date_str and visit_time_str:
            # Combine date and time
            appointment_datetime = datetime.fromisoformat(
                f"{visit_date_str}T{visit_time_str}"
            )
        else:
            raise HTTPException(
                status_code=400, detail="Visit date and time are required"
            )

        # Create appointment (we'll use the first unit type of the property for now)
        unit_type = property.unit_types[0] if property.unit_types else None
        if not unit_type:
            raise HTTPException(
                status_code=400, detail="No unit types available for this property"
            )

        new_appointment = Appointment(
            user_id=user_id,
            unit_type_id=unit_type.id,
            appointment_date=appointment_datetime,
            status=AppointmentStatus.pending,
            type=BookingIntent.viewing,
            admin_notes=f"Site visit request: {request.get('special_requests', '')}",
        )

        db.add(new_appointment)
        db.commit()
        db.refresh(new_appointment)

        # 4. Send notification if phone provided
        if request.get("contact_phone"):
            # Prepare site visit data for notification
            site_visit_data = {
                "contact_name": request.get("contact_name", "Valued Customer"),
                "visit_date": visit_date_str,
                "visit_time": visit_time_str,
                "property_name": property.name,
                "property_address": f"{property.address}, {property.city}"
                if property.address
                else f"{property.city}",
                "special_requests": request.get("special_requests", ""),
            }

            # Use background tasks like other endpoints
            if background_tasks:
                background_tasks.add_task(
                    send_site_visit_request_notification,
                    request["contact_phone"],
                    site_visit_data,
                )
            else:
                # Fallback if background tasks not available
                send_site_visit_request_notification(
                    request["contact_phone"], site_visit_data
                )

        return {
            "message": "Site visit request submitted successfully",
            "appointment_id": new_appointment.id,
            "notification_sent": bool(
                background_tasks and request.get("contact_phone")
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to create site visit: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create site visit: {str(e)}"
        )


# --- NOTIFICATION ENDPOINTS ---


@app.post("/notifications/send-booking-confirmation")
def send_booking_confirmation_notification(
    phone: str,
    venue_name: str,
    event_date: str,
    total_cost: float,
    background_tasks: BackgroundTasks,
):
    """
    Send booking confirmation notification
    """
    booking_data = {
        "venue_name": venue_name,
        "event_date": event_date,
        "total_cost": total_cost,
    }

    # Run in background to not block the API response
    background_tasks.add_task(send_booking_confirmation, phone, booking_data)

    return {"message": "Booking confirmation notification queued"}


@app.post("/notifications/send-booking-reminder")
def send_booking_reminder_notification(
    phone: str,
    venue_name: str,
    event_date: str,
    days_until: int,
    background_tasks: BackgroundTasks,
):
    """
    Send booking reminder notification
    """
    booking_data = {
        "venue_name": venue_name,
        "event_date": event_date,
        "days_until": days_until,
    }

    background_tasks.add_task(send_booking_reminder, phone, booking_data)

    return {"message": "Booking reminder notification queued"}


@app.post("/notifications/send-payment-reminder")
def send_payment_reminder_notification(
    phone: str,
    venue_name: str,
    amount_due: float,
    due_date: str,
    background_tasks: BackgroundTasks,
):
    """
    Send payment reminder notification
    """
    booking_data = {
        "venue_name": venue_name,
        "amount_due": amount_due,
        "due_date": due_date,
    }

    background_tasks.add_task(send_payment_reminder, phone, booking_data)

    return {"message": "Payment reminder notification queued"}


@app.post("/notifications/send-custom")
def send_custom_notification_endpoint(
    phone: str, message: str, background_tasks: BackgroundTasks
):
    """
    Send custom notification message
    """
    background_tasks.add_task(send_custom_notification, phone, message)

    return {"message": "Custom notification queued"}


@app.post("/notifications/send-site-visit-confirmation")
def send_site_visit_confirmation_endpoint(
    phone: str,
    contact_name: str,
    visit_date: str,
    visit_time: str,
    property_name: str,
    property_address: str,
    background_tasks: BackgroundTasks,
):
    """
    Send site visit confirmation notification
    """
    site_visit_data = {
        "contact_name": contact_name,
        "visit_date": visit_date,
        "visit_time": visit_time,
        "property_name": property_name,
        "property_address": property_address,
    }

    background_tasks.add_task(
        send_site_visit_confirmation_notification, phone, site_visit_data
    )

    return {"message": "Site visit confirmation notification queued"}


@app.post("/notifications/send-unit-available")
def send_unit_available_endpoint(
    phone: str,
    contact_name: str,
    property_name: str,
    unit_name: str,
    price: float,
    background_tasks: BackgroundTasks,
):
    """
    Send unit availability notification
    """
    unit_data = {
        "contact_name": contact_name,
        "property_name": property_name,
        "unit_name": unit_name,
        "price": price,
    }

    background_tasks.add_task(send_unit_available_notification, phone, unit_data)

    return {"message": "Unit availability notification queued"}


@app.post("/notifications/send-site-visit-reminder")
def send_site_visit_reminder_endpoint(
    phone: str,
    contact_name: str,
    visit_date: str,
    visit_time: str,
    property_name: str,
    property_address: str,
    hours_until: int,
    background_tasks: BackgroundTasks,
):
    """
    Send site visit reminder notification
    """
    reminder_data = {
        "contact_name": contact_name,
        "visit_date": visit_date,
        "visit_time": visit_time,
        "property_name": property_name,
        "property_address": property_address,
        "hours_until": hours_until,
    }

    background_tasks.add_task(
        send_site_visit_reminder_notification, phone, reminder_data
    )

    return {"message": "Site visit reminder notification queued"}


@app.post("/notifications/send-welcome")
def send_welcome_endpoint(
    phone: str, first_name: str, background_tasks: BackgroundTasks
):
    """
    Send welcome notification to new users
    """
    user_data = {
        "first_name": first_name,
    }

    background_tasks.add_task(send_welcome_notification, phone, user_data)

    return {"message": "Welcome notification queued"}


@app.post("/notifications/send-verification")
def send_verification_endpoint(
    phone: str, code: str, background_tasks: BackgroundTasks
):
    """
    Send account verification notification
    """
    verification_data = {
        "code": code,
    }

    background_tasks.add_task(
        send_account_verification_notification, phone, verification_data
    )

    return {"message": "Verification notification queued"}


@app.post("/notifications/send-password-reset")
def send_password_reset_endpoint(
    phone: str, code: str, background_tasks: BackgroundTasks
):
    """
    Send password reset notification
    """
    reset_data = {
        "code": code,
    }

    background_tasks.add_task(send_password_reset_notification, phone, reset_data)

    return {"message": "Password reset notification queued"}


# --- ADMIN COMMUNICATION SETTINGS ---


@app.get("/communication-settings")
def get_public_communication_settings():
    """Get public communication settings for clients"""
    return {
        "whatsapp_number": os.getenv("ADMIN_WHATSAPP_NUMBER", "+254754096684"),
        "support_phone": os.getenv("SUPPORT_PHONE", "+254700000000"),
        "support_email": os.getenv("SUPPORT_EMAIL", "support@victor-springs.com"),
        "company_name": os.getenv("COMPANY_NAME", "Victor Springs"),
        "floating_widget_enabled": os.getenv("FLOATING_WIDGET_ENABLED", "true").lower() == "true",
    }


@app.get("/admin/communication-settings")
def get_communication_settings(current_user: User = Depends(get_current_user)):
    """Get current communication settings"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return {
        "whatsapp_number": os.getenv("ADMIN_WHATSAPP_NUMBER", ""),
        "sms_api_key": os.getenv("HTTPSMS_API_KEY", ""),
        "sms_sender_phone": os.getenv("SENDER_PHONE", ""),
        "whatsapp_bridge_url": os.getenv(
            "WHATSAPP_BRIDGE_URL", "http://localhost:3001"
        ),
        "test_phone": os.getenv("TEST_PHONE", ""),
        "support_phone": os.getenv("SUPPORT_PHONE", "+254 700 000 000"),
        "website_url": os.getenv("WEBSITE_URL", "https://victor-springs.com"),
        "company_name": os.getenv("COMPANY_NAME", "Victor Springs"),
        "support_email": os.getenv("SUPPORT_EMAIL", "support@victor-springs.com"),
        "floating_widget_enabled": os.getenv("FLOATING_WIDGET_ENABLED", "true").lower() == "true",
    }


@app.post("/admin/communication-settings")
def update_communication_settings(
    settings: dict, current_user: User = Depends(get_current_user)
):
    """Update communication settings"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Update environment variables (in a real app, you'd save to database)
    env_vars = {
        "ADMIN_WHATSAPP_NUMBER": settings.get("whatsapp_number", ""),
        "HTTPSMS_API_KEY": settings.get("sms_api_key", ""),
        "SENDER_PHONE": settings.get("sms_sender_phone", ""),
        "WHATSAPP_BRIDGE_URL": settings.get(
            "whatsapp_bridge_url", "http://localhost:3001"
        ),
        "TEST_PHONE": settings.get("test_phone", ""),
    }

    # Update .env file
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()

        # Update or add variables
        updated_lines = []
        for line in lines:
            key = line.split("=")[0].strip()
            if key in env_vars:
                updated_lines.append(f"{key}={env_vars[key]}\n")
                del env_vars[key]
            else:
                updated_lines.append(line)

        # Add new variables
        for key, value in env_vars.items():
            updated_lines.append(f"{key}={value}\n")

        with open(env_path, "w") as f:
            f.writelines(updated_lines)

        return {"message": "Communication settings updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update settings: {str(e)}"
        )


@app.get("/admin/whatsapp-bridge-status")
def get_whatsapp_bridge_status(current_user: User = Depends(get_current_user)):
    """Check WhatsApp bridge connection status"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    bridge_url = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3001")
    try:
        import requests

        response = requests.get(f"{bridge_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "connected"
                if data.get("active_connections", 0) > 0
                else "running",
                "active_connections": data.get("active_connections", 0),
                "mapped_messages": data.get("mapped_messages", 0),
            }
        else:
            return {"status": "error", "message": "Bridge not responding"}
    except Exception as e:
        return {"status": "disconnected", "message": str(e)}


@app.post("/admin/connect-whatsapp")
def connect_whatsapp(current_user: User = Depends(get_current_user)):
    """Generate QR code for WhatsApp connection"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # In a real implementation, you'd trigger the bridge to generate a new QR code
    # For now, return a placeholder
    return {
        "message": "QR code generation initiated",
        "qr_code": "Placeholder: Run the bridge manually to see the actual QR code",
        "instructions": "Start the WhatsApp bridge with 'npm start' in the notification_service directory",
    }


@app.post("/admin/test-connection")
def test_communication_connection(
    test_data: dict, current_user: User = Depends(get_current_user)
):
    """Test communication connection by sending a test message"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    phone = test_data.get("phone", "")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")

    # Try to send a test notification
    try:
        success, method = send_custom_notification(
            phone,
            "🧪 Victor Springs - Test Message\n\nThis is a test message from your admin panel. If you received this, your communication settings are working correctly!",
        )

        if success:
            return {"message": f"Test message sent successfully via {method}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


# --- NOTIFICATION MANAGER ENDPOINTS ---


@app.get("/admin/bookings-with-phones")
def get_bookings_with_phones(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get bookings with user phone numbers for notification management"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Join bookings with users to get phone numbers
        bookings = db.query(Appointment).join(User).join(UnitType).join(Property).all()

        result = []
        for booking in bookings:
            result.append(
                {
                    "id": booking.id,
                    "user_name": f"{booking.user.first_name} {booking.user.last_name}",
                    "user_email": booking.user.email,
                    "user_phone": booking.user.phone_number,
                    "property_name": booking.unit_type.property.name,
                    "unit_type": booking.unit_type.name,
                    "appointment_date": booking.appointment_date.isoformat(),
                    "notification_status": "pending",  # This would be tracked in a real system
                    "status": "confirmed" if booking.admin_notes else "pending",
                }
            )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch bookings: {str(e)}"
        )


@app.post("/admin/send-notification")
def send_booking_notification(
    notification_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send notification to booking customer"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    booking_id = notification_data.get("booking_id")
    notification_type = notification_data.get("type")
    custom_message = notification_data.get("custom_message", "")

    try:
        # Get booking with user details
        booking = (
            db.query(Appointment)
            .join(User)
            .filter(Appointment.id == booking_id)
            .first()
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        phone = booking.user.phone_number
        if not phone:
            raise HTTPException(status_code=400, detail="User has no phone number")

        # Prepare message based on type
        if notification_type == "confirmation":
            message = f"""🏛️ Victor Springs - Booking Confirmed!

Dear {booking.user.first_name},

Your site visit booking has been confirmed!

📅 Date: {booking.appointment_date.strftime("%Y-%m-%d %H:%M")}
🏠 Property: {booking.unit_type.property.name}
🏢 Unit: {booking.unit_type.name}

Please arrive 15 minutes early. Our team will be ready to assist you.

Questions? Call us: +254 700 000 000

Thank you for choosing Victor Springs!"""

        elif notification_type == "reminder":
            message = f"""⏰ Victor Springs - Site Visit Reminder!

Hi {booking.user.first_name},

This is a reminder about your upcoming site visit:

📅 Date: {booking.appointment_date.strftime("%Y-%m-%d %H:%M")}
🏠 Property: {booking.unit_type.property.name}
🏢 Unit: {booking.unit_type.name}

Please bring valid ID and any specific requirements mentioned during booking.

See you soon!
📞 +254 700 000 000"""

        elif notification_type == "custom":
            message = custom_message
        else:
            raise HTTPException(status_code=400, detail="Invalid notification type")

        # Send notification (tries WhatsApp first, then SMS)
        success, method = send_custom_notification(phone, message)

        if success:
            return {"message": f"Notification sent via {method}", "method": method}
        else:
            raise HTTPException(status_code=500, detail="Failed to send notification")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to send notification: {str(e)}"
        )


# --- MESSAGE TEMPLATES MANAGEMENT ---

DEFAULT_MESSAGE_TEMPLATES = {
    "site_visit_request": {
        "subject": "Site Visit Request Received",
        "message": """🏛️ Victor Springs - Site Visit Request Received!

Hi {contact_name},

Thank you for your interest in Victor Springs! Your site visit request has been received and is awaiting approval.

📅 Preferred Date: {visit_date}
⏰ Preferred Time: {visit_time}
🏠 Property: {property_name}
📝 Special Requests: {special_requests}

Our team will review your request and confirm the appointment soon. You can track the status by signing into your account at {website_url}.

Questions? Call us: {support_phone}

Thank you for choosing Victor Springs!
🌟 Your Dream Home Awaits""",
        "variables": [
            "contact_name",
            "visit_date",
            "visit_time",
            "property_name",
            "special_requests",
            "website_url",
            "support_phone",
        ],
    },
    "site_visit_confirmation": {
        "subject": "Site Visit Confirmed",
        "message": """✅ Victor Springs - Site Visit Confirmed!

Hi {contact_name},

Great news! Your site visit has been confirmed!

📅 Date: {visit_date}
⏰ Time: {visit_time}
🏠 Property: {property_name}
📍 Address: {property_address}

What to bring:
• Valid ID
• Any specific requirements mentioned during booking
• Comfortable walking shoes

Please arrive 15 minutes early. Our team will be ready to welcome you!

Questions? Call us: {support_phone}

We're excited to help you find your perfect home!
🏡 Victor Springs""",
        "variables": [
            "contact_name",
            "visit_date",
            "visit_time",
            "property_name",
            "property_address",
            "support_phone",
        ],
    },
    "express_interest": {
        "subject": "Interest Recorded",
        "message": """💝 Victor Springs - Interest Recorded!

Hi {contact_name},

Thank you for expressing interest in {property_name}!

✅ Your interest has been recorded in our system
⏰ We'll notify you when units become available within {timeframe}
📝 Your notes: {special_requests}

To track your requests and get updates, please sign in to your account at {website_url}.

Questions? Call us: {support_phone}

Thank you for choosing Victor Springs!
🌟 Your Dream Home Journey Starts Here""",
        "variables": [
            "contact_name",
            "property_name",
            "timeframe",
            "special_requests",
            "website_url",
            "support_phone",
        ],
    },
    "unit_available": {
        "subject": "Unit Now Available",
        "message": """🎉 Victor Springs - Unit Now Available!

Hi {contact_name},

Exciting news! A unit you're interested in is now available!

🏠 Property: {property_name}
🏢 Unit: {unit_name}
💰 Price: KES {price} per month

This is a limited-time availability. Contact us immediately to secure this unit!

📞 Call now: {support_phone}
💬 Or reply to this message

Don't miss this opportunity!
🏡 Victor Springs""",
        "variables": [
            "contact_name",
            "property_name",
            "unit_name",
            "price",
            "support_phone",
        ],
    },
    "site_visit_reminder": {
        "subject": "Site Visit Reminder",
        "message": """⏰ Victor Springs - Site Visit Reminder!

Hi {contact_name},

This is a friendly reminder about your upcoming site visit!

📅 Date: {visit_date}
⏰ Time: {visit_time} (in {hours_until} hours)
🏠 Property: {property_name}
📍 Address: {property_address}

What to bring:
• Valid ID
• Any specific requirements
• Comfortable walking shoes

Please arrive 15 minutes early. Our team is excited to show you around!

Questions? Call us: {support_phone}

See you soon!
🏡 Victor Springs""",
        "variables": [
            "contact_name",
            "visit_date",
            "visit_time",
            "hours_until",
            "property_name",
            "property_address",
            "support_phone",
        ],
    },
    "welcome": {
        "subject": "Welcome to Victor Springs",
        "message": """🎉 Welcome to Victor Springs!

Hi {first_name},

Welcome to Victor Springs - Your Gateway to Premium Living!

🏠 Discover our exclusive properties in Nairobi
💰 Competitive pricing with flexible payment plans
🏢 Modern units with world-class amenities
🌟 Exceptional customer service

Explore our properties at {website_url} or call us at {support_phone}.

Your dream home awaits!
🏡 Victor Springs""",
        "variables": ["first_name", "website_url", "support_phone"],
    },
    "account_verification": {
        "subject": "Account Verification",
        "message": """🔐 Victor Springs - Account Verification

Your verification code is: {code}

Please enter this code to verify your account.

This code expires in 10 minutes.

Questions? Call us: {support_phone}

🏡 Victor Springs""",
        "variables": ["code", "support_phone"],
    },
    "password_reset": {
        "subject": "Password Reset",
        "message": """🔑 Victor Springs - Password Reset

Your password reset code is: {code}

Use this code to reset your password.

This code expires in 15 minutes.

If you didn't request this reset, please ignore this message.

Questions? Call us: {support_phone}

🏡 Victor Springs""",
        "variables": ["code", "support_phone"],
    },
}


@app.get("/admin/message-templates")
def get_message_templates(current_user: User = Depends(get_current_user)):
    """Get all message templates"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # In a real app, you'd load these from database
    # For now, return defaults merged with any customizations
    return DEFAULT_MESSAGE_TEMPLATES


@app.post("/admin/message-templates/{template_key}")
def update_message_template(
    template_key: str,
    template_data: dict,
    current_user: User = Depends(get_current_user),
):
    """Update a specific message template"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if template_key not in DEFAULT_MESSAGE_TEMPLATES:
        raise HTTPException(status_code=404, detail="Template not found")

    # In a real app, you'd save to database
    # For now, just validate and return success
    required_fields = ["subject", "message"]
    for field in required_fields:
        if field not in template_data:
            raise HTTPException(
                status_code=400, detail=f"Missing required field: {field}"
            )

    return {"message": f"Template '{template_key}' updated successfully"}


@app.get("/admin/global-settings")
def get_global_settings(current_user: User = Depends(get_current_user)):
    """Get global settings used in message templates"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return {
        "support_phone": os.getenv("SUPPORT_PHONE", "+254 700 000 000"),
        "website_url": os.getenv("WEBSITE_URL", "https://victor-springs.com"),
        "company_name": os.getenv("COMPANY_NAME", "Victor Springs"),
        "support_email": os.getenv("SUPPORT_EMAIL", "support@victor-springs.com"),
    }


@app.post("/admin/global-settings")
def update_global_settings(
    settings: dict, current_user: User = Depends(get_current_user)
):
    """Update global settings"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Update environment variables
    env_vars = {
        "SUPPORT_PHONE": settings.get("support_phone", "+254 700 000 000"),
        "WEBSITE_URL": settings.get("website_url", "https://victor-springs.com"),
        "COMPANY_NAME": settings.get("company_name", "Victor Springs"),
        "SUPPORT_EMAIL": settings.get("support_email", "support@victor-springs.com"),
        "FLOATING_WIDGET_ENABLED": str(settings.get("floating_widget_enabled", True)).lower(),
    }

    # Update .env file
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()

        updated_lines = []
        for line in lines:
            key = line.split("=")[0].strip()
            if key in env_vars:
                updated_lines.append(f"{key}={env_vars[key]}\n")
                del env_vars[key]
            else:
                updated_lines.append(line)

        # Add new variables
        for key, value in env_vars.items():
            updated_lines.append(f"{key}={value}\n")

        with open(env_path, "w") as f:
            f.writelines(updated_lines)

        return {"message": "Global settings updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update settings: {str(e)}"
        )


@app.get("/user/interests")
def get_user_interests(Authorization: str = Header(...), db: Session = Depends(get_db)):
    """Get property interests for the current user"""
    # Extract token from Authorization header
    auth_header = Authorization
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = Authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Find user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get user's vacancy alerts with related data
        interests = db.query(VacancyAlert).filter(VacancyAlert.user_id == user.id).all()

        result = []
        for interest in interests:
            # Get unit type and property info safely
            unit_type = db.query(UnitType).filter(UnitType.id == interest.unit_type_id).first()
            property_name = "Unknown Property"
            unit_type_name = "Unknown Unit"

            if unit_type:
                unit_type_name = unit_type.name or "Unknown Unit"
                property_obj = db.query(Property).filter(Property.id == unit_type.property_id).first()
                if property_obj:
                    property_name = property_obj.name or "Unknown Property"

            result.append({
                "id": interest.id,
                "user_id": interest.user_id,
                "guest_id": interest.guest_id,
                "property_id": property_obj.id if property_obj else None,
                "property_name": property_name,
                "unit_type_name": unit_type_name,
                "contact_name": interest.contact_name,
                "contact_email": interest.contact_email,
                "contact_phone": interest.contact_phone,
                "timeframe_months": max(0, (interest.valid_until - datetime.now().date()).days // 30),
                "special_requests": interest.special_requests,
                "created_at": interest.created_at.isoformat() if interest.created_at else None,
                "is_active": interest.is_active,
            })

        return result

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Error fetching user interests: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/appointments/my-appointments")
def get_user_appointments(Authorization: str = Header(...), db: Session = Depends(get_db)):
    """Get appointments for the current user"""
    # Extract token from Authorization header
    auth_header = Authorization
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = Authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Find user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get user's appointments with venue information
        appointments = db.query(Appointment).filter(Appointment.user_id == user.id).all()

        # Add property information to each appointment
        result = []
        for appointment in appointments:
            unit_type = db.query(UnitType).filter(UnitType.id == appointment.unit_type_id).first()
            property_name = "Unknown Property"
            unit_type_name = "Unknown Unit"

            if unit_type:
                unit_type_name = unit_type.name or "Unknown Unit"
                property_obj = db.query(Property).filter(Property.id == unit_type.property_id).first()
                if property_obj:
                    property_name = property_obj.name or "Unknown Property"

            appointment_dict = {
                "id": appointment.id,
                "user_id": appointment.user_id,
                "unit_type_id": appointment.unit_type_id,
                "appointment_date": appointment.appointment_date.isoformat() if appointment.appointment_date else None,
                "status": appointment.status.value if appointment.status else "Pending",
                "type": appointment.type.value if appointment.type else "viewing",
                "admin_notes": appointment.admin_notes,
                "created_at": appointment.created_at.isoformat() if appointment.created_at else None,
                "unit_type_name": unit_type_name,
                "property_name": property_name,
            }
            result.append(appointment_dict)

        return result

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Error fetching user appointments: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/appointments/{appointment_id}")
def delete_user_appointment(appointment_id: int, Authorization: str = Header(...), db: Session = Depends(get_db)):
    """Delete/cancel a user appointment"""
    # Extract token from Authorization header
    auth_header = Authorization
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Find user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Find and delete the appointment (only if it belongs to the user)
        appointment = db.query(Appointment).filter(
            Appointment.id == appointment_id,
            Appointment.user_id == user.id
        ).first()

        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        db.delete(appointment)
        db.commit()
        return {"message": "Appointment cancelled successfully"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/admin/property-interests")
def get_property_interests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all property interests for admin"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Get all vacancy alerts with related data
        interests = db.query(VacancyAlert).join(UnitType).join(Property).all()

        result = []
        for interest in interests:
            result.append({
                "id": interest.id,
                "user_id": interest.user_id,
                "guest_id": interest.guest_id,
                "property_name": interest.unit_type.property.name,
                "unit_type_name": interest.unit_type.name,
                "contact_name": interest.contact_name,
                "contact_email": interest.contact_email,
                "contact_phone": interest.contact_phone,
                "timeframe_months": (interest.valid_until - datetime.now().date()).days // 30,
                "special_requests": interest.special_requests,
                "created_at": interest.created_at.isoformat(),
                "is_active": interest.is_active,
            })

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch interests: {str(e)}")


@app.delete("/admin/property-interests/{interest_id}")
def delete_property_interest(interest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a property interest"""
    if current_user.role.value != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        interest = db.query(VacancyAlert).filter(VacancyAlert.id == interest_id).first()
        if not interest:
            raise HTTPException(status_code=404, detail="Interest not found")

        db.delete(interest)
        db.commit()

        return {"message": "Interest deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete interest: {str(e)}")


@app.post("/notifications/test")
def test_notifications(phone: Optional[str] = None):
    """
    Test notification system with your phone number
    """
    test_phone = phone or os.getenv("TEST_PHONE", "0754096684")
    test_booking = {
        "venue_name": "Nairobi Arboretum",
        "event_date": "2024-12-15 14:00",
        "total_cost": 50000,
    }

    success, method = send_booking_confirmation(test_phone, test_booking)

    return {
        "message": f"Test notification sent via {method}",
        "success": success,
        "phone": test_phone,
        "method": method,
    }
