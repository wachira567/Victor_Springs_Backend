import os
import requests
from datetime import datetime
from sms_gateway import send_sms
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

WHATSAPP_BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3001")


def send_whatsapp_message(phone, text):
    """
    Send message via WhatsApp bridge
    """
    try:
        resp = requests.post(
            f"{WHATSAPP_BRIDGE_URL}/send-whatsapp",
            json={"phone": phone, "message": text},
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"📱 WhatsApp sent to {phone}")
            return True, "whatsapp"
        else:
            print(f"❌ WhatsApp failed: {resp.text}")
            return False, "whatsapp"
    except Exception as e:
        print(f"❌ WhatsApp bridge error: {e}")
        return False, "whatsapp"


def notify_user(phone, message, booking_details=None):
    """
    Send notification to user - tries WhatsApp first, then SMS fallback

    Args:
        phone: Phone number (07... or +254... format)
        message: The message to send
        booking_details: Optional dict with booking info for logging
    """
    print(f"\n--- Victor Springs Notification for {phone} ---")
    print(f"Message: {message[:50]}...")

    if booking_details:
        print(f"Booking: {booking_details}")

    # 1. Try WhatsApp first
    print("Attempting WhatsApp...")
    wa_success, method = send_whatsapp_message(phone, message)

    if wa_success:
        print("✅ Notification sent via WhatsApp")
        return True, "whatsapp"
    else:
        # 2. Fallback to SMS
        print("WhatsApp failed. Falling back to SMS...")
        sms_success = send_sms(phone, message)
        if sms_success:
            print("✅ Notification sent via SMS")
            return True, "sms"
        else:
            print("❌ Both WhatsApp and SMS failed")
            return False, "failed"


def send_booking_confirmation(phone, booking_data):
    """
    Send booking confirmation notification
    """
    venue_name = booking_data.get("venue_name", "Venue")
    event_date = booking_data.get("event_date", "TBD")
    total_cost = booking_data.get("total_cost", 0)

    message = f"""🏛️ Victor Springs - Booking Confirmed!

Dear valued customer,

Your booking for {venue_name} has been confirmed!

📅 Event Date: {event_date}
💰 Total Amount: KES {total_cost:,.0f}

Please arrive 30 minutes early for your site visit.
Our team will contact you shortly with additional details.

Thank you for choosing Victor Springs!
📞 Support: +254 700 000 000
"""

    return notify_user(phone, message, booking_data)


def send_booking_reminder(phone, booking_data):
    """
    Send booking reminder notification
    """
    venue_name = booking_data.get("venue_name", "Venue")
    event_date = booking_data.get("event_date", "TBD")
    days_until = booking_data.get("days_until", 1)

    message = f"""⏰ Victor Springs - Booking Reminder!

Hi there,

This is a friendly reminder about your upcoming site visit:

🏛️ Venue: {venue_name}
📅 Date: {event_date}
⏳ Days remaining: {days_until}

Please confirm your availability or contact us if you need to reschedule.

We're excited to host your special event!

📞 Call us: +254 700 000 000
"""

    return notify_user(phone, message, booking_data)


def send_payment_reminder(phone, booking_data):
    """
    Send payment reminder notification
    """
    venue_name = booking_data.get("venue_name", "Venue")
    amount_due = booking_data.get("amount_due", 0)
    due_date = booking_data.get("due_date", "ASAP")

    message = f"""💳 Victor Springs - Payment Reminder!

Dear customer,

We hope you're excited about your upcoming event at {venue_name}!

Please note that payment of KES {amount_due:,.0f} is due by {due_date}.

💰 Payment Methods:
- M-Pesa: Paybill 123456 (Account: Your Booking ID)
- Bank Transfer: Details will be shared upon request

Contact us immediately if you need assistance.

Thank you for your prompt attention!

📞 Support: +254 700 000 000
"""

    return notify_user(phone, message, booking_data)


def send_site_visit_request_notification(phone, site_visit_data):
    """
    Send notification when user requests a site visit
    """
    contact_name = site_visit_data.get("contact_name", "Valued Customer")
    visit_date = site_visit_data.get("visit_date", "TBD")
    visit_time = site_visit_data.get("visit_time", "TBD")
    property_name = site_visit_data.get("property_name", "Victor Springs Property")
    special_requests = site_visit_data.get("special_requests", "")

    message = f"""🏛️ Victor Springs - Site Visit Request Received!

Hi {contact_name},

Thank you for your interest in Victor Springs! Your site visit request has been received and is awaiting approval.

📅 Preferred Date: {visit_date}
⏰ Preferred Time: {visit_time}
🏠 Property: {property_name}
{f"📝 Special Requests: {special_requests}" if special_requests else ""}

Our team will review your request and confirm the appointment soon. You can track the status by signing into your account at victor-springs.com.

Questions? Call us: +254 700 000 000

Thank you for choosing Victor Springs!
🌟 Your Dream Home Awaits"""

    return notify_user(phone, message, site_visit_data)


def send_site_visit_confirmation_notification(phone, site_visit_data):
    """
    Send notification when admin confirms a site visit
    """
    contact_name = site_visit_data.get("contact_name", "Valued Customer")
    visit_date = site_visit_data.get("visit_date", "TBD")
    visit_time = site_visit_data.get("visit_time", "TBD")
    property_name = site_visit_data.get("property_name", "Victor Springs Property")
    property_address = site_visit_data.get("property_address", "Nairobi, Kenya")

    message = f"""✅ Victor Springs - Site Visit Confirmed!

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

Please arrive 15 minutes early. Our team will be ready to welcome you and show you around.

Questions? Call us: +254 700 000 000

We're excited to help you find your perfect home!
🏡 Victor Springs"""

    return notify_user(phone, message, site_visit_data)


def send_express_interest_notification(phone, interest_data):
    """
    Send notification when user expresses interest in a unit
    """
    contact_name = interest_data.get("contact_name", "Valued Customer")
    property_name = interest_data.get("property_name", "Victor Springs Property")
    timeframe = interest_data.get("timeframe", "3 months")
    special_requests = interest_data.get("special_requests", "")

    message = f"""💝 Victor Springs - Interest Recorded!

Hi {contact_name},

Thank you for expressing interest in {property_name}!

✅ Your interest has been recorded in our system
⏰ We'll notify you when units become available within {timeframe}
{f"📝 Your notes: {special_requests}" if special_requests else ""}

To track your requests and get updates, please sign in to your account at victor-springs.com.

Questions? Call us: +254 700 000 000

Thank you for choosing Victor Springs!
🌟 Your Dream Home Journey Starts Here"""

    return notify_user(phone, message, interest_data)


def send_unit_available_notification(phone, unit_data):
    """
    Send notification when a unit becomes available for waitlist users
    """
    contact_name = unit_data.get("contact_name", "Valued Customer")
    property_name = unit_data.get("property_name", "Victor Springs Property")
    unit_name = unit_data.get("unit_name", "Unit")
    price = unit_data.get("price", "TBD")

    message = f"""🎉 Victor Springs - Unit Now Available!

Hi {contact_name},

Exciting news! A unit you're interested in is now available!

🏠 Property: {property_name}
🏢 Unit: {unit_name}
💰 Price: KES {price:,.0f} per month

This is a limited-time availability. Contact us immediately to secure this unit!

📞 Call now: +254 700 000 000
💬 Or reply to this message

Don't miss this opportunity!
🏡 Victor Springs"""

    return notify_user(phone, message, unit_data)


def send_site_visit_reminder_notification(phone, reminder_data):
    """
    Send reminder notification a few hours before site visit
    """
    contact_name = reminder_data.get("contact_name", "Valued Customer")
    visit_date = reminder_data.get("visit_date", "Today")
    visit_time = reminder_data.get("visit_time", "TBD")
    property_name = reminder_data.get("property_name", "Victor Springs Property")
    property_address = reminder_data.get("property_address", "Nairobi, Kenya")
    hours_until = reminder_data.get("hours_until", 2)

    message = f"""⏰ Victor Springs - Site Visit Reminder!

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

Questions? Call us: +254 700 000 000

See you soon!
🏡 Victor Springs"""

    return notify_user(phone, message, reminder_data)


def send_welcome_notification(phone, user_data):
    """
    Send welcome message to new users
    """
    first_name = user_data.get("first_name", "Valued Customer")

    message = f"""🎉 Welcome to Victor Springs!

Hi {first_name},

Welcome to Victor Springs - Your Gateway to Premium Living!

🏠 Discover our exclusive properties in Nairobi
💰 Competitive pricing with flexible payment plans
🏢 Modern units with world-class amenities
🌟 Exceptional customer service

Explore our properties at victor-springs.com or call us at +254 700 000 000.

Your dream home awaits!
🏡 Victor Springs"""

    return notify_user(phone, message, user_data)


def send_account_verification_notification(phone, verification_data):
    """
    Send account verification notification
    """
    verification_code = verification_data.get("code", "XXXXXX")

    message = f"""🔐 Victor Springs - Account Verification

Your verification code is: {verification_code}

Please enter this code to verify your account.

This code expires in 10 minutes.

Questions? Call us: +254 700 000 000

🏡 Victor Springs"""

    return notify_user(phone, message, verification_data)


def send_password_reset_notification(phone, reset_data):
    """
    Send password reset notification
    """
    reset_code = reset_data.get("code", "XXXXXX")

    message = f"""🔑 Victor Springs - Password Reset

Your password reset code is: {reset_code}

Use this code to reset your password.

This code expires in 15 minutes.

If you didn't request this reset, please ignore this message.

Questions? Call us: +254 700 000 000

🏡 Victor Springs"""

    return notify_user(phone, message, reset_data)


def send_custom_notification(phone, message, booking_data=None):
    """
    Send custom notification message
    """
    return notify_user(phone, message, booking_data)


# Test function
if __name__ == "__main__":
    # Test with your number
    test_phone = os.getenv("TEST_PHONE", "0754096684")
    test_booking = {
        "venue_name": "Nairobi Arboretum",
        "event_date": "2024-12-15 14:00",
        "total_cost": 50000,
    }

    print("🧪 Testing Victor Springs Notification Service...")
    success, method = send_booking_confirmation(test_phone, test_booking)
    print(f"Test result: {success} via {method}")
