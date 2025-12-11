import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment
ANDROID_API_KEY = os.getenv("HTTPSMS_API_KEY")
SENDER_PHONE = os.getenv("SENDER_PHONE", "+254754096684")  # Your Airtel number


def send_sms(phone_number, message):
    """
    Send SMS using httpSMS Android app
    """
    if not ANDROID_API_KEY:
        print("❌ HTTPSMS_API_KEY not found in environment variables")
        return False

    url = "https://api.httpsms.com/v1/messages/send"

    # Ensure phone number is in +254 format
    if phone_number.startswith("0"):
        phone_number = "+254" + phone_number[1:]
    elif not phone_number.startswith("+"):
        phone_number = "+" + phone_number

    payload = {
        "content": message,
        "from": SENDER_PHONE,
        "to": phone_number,
    }

    headers = {"x-api-key": ANDROID_API_KEY, "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ SMS sent to {phone_number}")
            return True
        else:
            print(f"❌ SMS Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False


def format_phone_number(phone):
    """
    Helper function to format phone numbers consistently
    """
    if phone.startswith("0"):
        return "+254" + phone[1:]
    elif not phone.startswith("+"):
        return "+" + phone
    return phone
