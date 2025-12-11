# Victor Springs Notification Service

This service provides automated WhatsApp and SMS notifications for the Victor Springs booking system, plus a live chat widget that connects website visitors directly to your WhatsApp.

## Features

- **WhatsApp Integration**: Send messages via WhatsApp using Baileys library
- **SMS Fallback**: Automatic fallback to SMS via httpSMS Android app
- **Live Chat Widget**: Website visitors can chat directly with admin via WhatsApp
- **Quoted Replies**: Smart reply routing using WhatsApp's quote feature
- **Booking Confirmations**: Automatic notifications when bookings are made
- **Custom Notifications**: API endpoints for custom messages
- **Background Processing**: Non-blocking notification sending

## Setup Instructions

### 1. Install Dependencies

```bash
cd VictorSprings_Backend/notification_service
npm install
```

### 2. Configure Android Phone for SMS

1. Download **httpSMS** app from Google Play Store
2. Create an account and get your API key
3. Configure battery optimization:
   - Samsung: Settings > Apps > httpSMS > Battery > Unrestricted
   - Tecno/Infinix: Settings > Special App Access > Battery Optimization > Don't optimize
4. Add the API key to your `.env` file as `HTTPSMS_API_KEY`

### 3. Start WhatsApp Bridge

```bash
cd VictorSprings_Backend/notification_service
npm start
# or
node whatsapp_bridge.js
```

1. Scan the QR code that appears with your WhatsApp
2. The bridge will show "WhatsApp Connected" when ready

### 4. Test the System

```bash
# Test with your phone number
curl -X POST http://localhost:8000/notifications/test

# Or test with a specific number
curl -X POST "http://localhost:8000/notifications/test?phone=0754096684"
```

## API Endpoints

### Send Booking Confirmation

```bash
POST /notifications/send-booking-confirmation
{
  "phone": "0754096684",
  "venue_name": "Nairobi Arboretum",
  "event_date": "2024-12-15 14:00",
  "total_cost": 50000
}
```

### Send Booking Reminder

```bash
POST /notifications/send-booking-reminder
{
  "phone": "0754096684",
  "venue_name": "Nairobi Arboretum",
  "event_date": "2024-12-15 14:00",
  "days_until": 3
}
```

### Send Payment Reminder

```bash
POST /notifications/send-payment-reminder
{
  "phone": "0754096684",
  "venue_name": "Nairobi Arboretum",
  "amount_due": 25000,
  "due_date": "2024-12-10"
}
```

### Send Custom Message

```bash
POST /notifications/send-custom
{
  "phone": "0754096684",
  "message": "Your custom message here"
}
```

## Environment Variables

Add these to your `VictorSprings_Backend/.env` file:

```env
# WhatsApp Bridge
WHATSAPP_BRIDGE_URL=http://localhost:3001

# SMS Gateway (httpSMS)
HTTPSMS_API_KEY=your_httpsms_api_key_here
SENDER_PHONE=+254754096684

# Testing
TEST_PHONE=0754096684
```

## Architecture

1. **whatsapp_bridge.js**: Node.js server that connects to WhatsApp Web
2. **sms_gateway.py**: Python module for SMS sending via httpSMS
3. **notification_service.py**: Main service coordinating WhatsApp/SMS sending
4. **app.py**: FastAPI endpoints for triggering notifications

## Message Flow

1. API receives notification request
2. Tries WhatsApp first via local bridge
3. If WhatsApp fails, falls back to SMS
4. Returns success/failure status

## Live Chat Widget

The chat widget allows website visitors to chat directly with you via WhatsApp without leaving the website.

### How It Works

1. **User Choice**: Visitors see a chat button and can choose between WhatsApp chat or Tawk.to
2. **WhatsApp Connection**: If they choose WhatsApp, the widget connects to your bridge
3. **Quoted Replies**: You reply by quoting the specific message in WhatsApp (swipe right)
4. **Smart Routing**: The system routes your reply back to the correct website visitor

### For Admin (You)

1. **Receive Messages**: All website chats appear in your WhatsApp as "👤 New Website Guest: [message]"
2. **Reply**: Swipe right on any message bubble to quote it, then type your reply
3. **Automatic Routing**: Your quoted reply goes back to the correct website visitor

### For Website Visitors

1. **Click Chat Button**: Green chat button in bottom-right corner
2. **Choose Method**: Select WhatsApp Direct or Live Chat
3. **Chat**: Type messages that go directly to your WhatsApp
4. **Receive Replies**: Get responses in real-time

### Fallback Behavior

- If WhatsApp bridge is unavailable, users see "feature currently unavailable"
- Tawk.to chat widget serves as backup option
- System gracefully handles connection failures

## Troubleshooting

### WhatsApp Issues

- Make sure the QR code is scanned with the correct WhatsApp account
- Check that the bridge is running on port 3001
- Verify phone number format (07... or +254...)

### SMS Issues

- Check httpSMS app is running and API key is correct
- Verify battery optimization is disabled
- Check phone number format

### Common Errors

- "WhatsApp bridge error": Bridge not running or unreachable
- "SMS Failed": API key invalid or httpSMS app not configured
- "Connection Error": Network issues

## Production Deployment

For production:

1. Run WhatsApp bridge on a VPS with persistent storage
2. Use a proper SMS gateway instead of httpSMS
3. Add proper logging and monitoring
4. Implement rate limiting and queue management
