# Victor Springs Backend

FastAPI backend for the Victor Springs property booking and rental system.

## Features

- **Property Management**: CRUD operations for properties and units
- **User Authentication**: JWT-based auth with Google OAuth integration
- **Booking System**: Appointment scheduling and management
- **Notification Service**: Automated WhatsApp/SMS notifications
- **Live Chat Widget**: Direct WhatsApp chat with admin from website
- **Waitlist Management**: Vacancy alerts and notifications

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL database
- Node.js 16+ (for notification service)
- Android phone with httpSMS app (for SMS notifications)

### Installation

1. **Clone and setup:**

   ```bash
   cd VictorSprings_Backend
   pip install -r requirements.txt
   ```

2. **Environment setup:**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Database setup:**

   ```bash
   # Run migrations
   alembic upgrade head
   ```

4. **Start the backend:**
   ```bash
   uvicorn app:app --reload
   ```

## Notification Service Setup

The notification service provides automated WhatsApp and SMS messaging.

### 1. Install Dependencies

```bash
cd notification_service
npm install
```

### 2. Configure SMS Gateway

1. Download **httpSMS** app on your Android phone
2. Create account and get API key
3. Disable battery optimization for the app
4. Add API key to `.env`:
   ```env
   HTTPSMS_API_KEY=your_api_key_here
   SENDER_PHONE=+254754096684
   ```

### 3. Start WhatsApp Bridge

```bash
./start_notification_service.sh
```

Or manually:

```bash
cd notification_service
npm start
```

Scan the QR code with WhatsApp to connect.

### 4. Start Chat Widget (Frontend)

The chat widget allows website visitors to chat directly with you via WhatsApp:

```bash
cd VictorSprings_Frontend
npm install  # Install socket.io-client
npm run dev
```

### 5. Test Notifications

```bash
# Test with your phone
curl -X POST http://localhost:8000/notifications/test

# Send booking confirmation
curl -X POST http://localhost:8000/notifications/send-booking-confirmation \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "0754096684",
    "venue_name": "Nairobi Arboretum",
    "event_date": "2024-12-15 14:00",
    "total_cost": 50000
  }'
```

## API Endpoints

### Authentication

- `POST /token` - Login
- `GET /login/google` - Google OAuth redirect
- `GET /auth/google/callback` - OAuth callback
- `GET /users/me` - Get current user

### Properties

- `GET /properties` - List all properties
- `GET /properties/{id}` - Get property details
- `GET /properties/{id}/booked-dates` - Get booked dates

### Bookings

- `POST /book-viewing` - Create booking (auto-sends confirmation)
- `POST /join-waitlist` - Join vacancy waitlist

### Notifications

- `POST /notifications/send-booking-confirmation` - Send confirmation
- `POST /notifications/send-booking-reminder` - Send reminder
- `POST /notifications/send-payment-reminder` - Send payment reminder
- `POST /notifications/send-custom` - Send custom message
- `POST /notifications/test` - Test notification system

## Environment Variables

```env
# Database
DATABASE_URL=postgresql+psycopg2://user:pass@localhost/victor_springs

# Security
SECRET_KEY=your-secret-key-here

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Frontend
FRONTEND_URL=http://localhost:5173

# Notifications
WHATSAPP_BRIDGE_URL=http://localhost:3001
HTTPSMS_API_KEY=your-httpsms-api-key
SENDER_PHONE=+254754096684
TEST_PHONE=0754096684

# Cloudinary (optional)
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

## Database Schema

- **Users**: Customer information and authentication
- **Properties**: Venue/property listings
- **UnitTypes**: Different unit types within properties
- **Appointments**: Booking records
- **VacancyAlerts**: Waitlist subscriptions

## Development

### Running Tests

```bash
pytest
```

### Database Migrations

```bash
alembic revision --autogenerate -m "migration message"
alembic upgrade head
```

### API Documentation

Visit `http://localhost:8000/docs` for interactive API docs.

## Production Deployment

1. Set up PostgreSQL database
2. Configure environment variables
3. Run database migrations
4. Start FastAPI with uvicorn/gunicorn
5. Set up WhatsApp bridge on persistent server
6. Configure reverse proxy (nginx)
7. Set up SSL certificates

## Troubleshooting

### Notification Issues

- **WhatsApp not connecting**: Check QR code scan, ensure bridge is running
- **SMS not sending**: Verify httpSMS API key and battery optimization
- **Bridge connection failed**: Check firewall, ensure port 3001 is accessible

### API Issues

- **CORS errors**: Check FRONTEND_URL in environment
- **Database connection**: Verify DATABASE_URL format
- **Google OAuth**: Check client ID/secret configuration

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## License

MIT License
