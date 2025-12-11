#!/bin/bash

# Victor Springs Notification Service Startup Script

echo "🚀 Starting Victor Springs Notification Service..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm first."
    exit 1
fi

# Navigate to notification service directory
cd notification_service

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install
fi

# Start WhatsApp bridge in background
echo "📱 Starting WhatsApp Bridge..."
npm start &

# Wait a moment for bridge to start
sleep 3

echo "✅ WhatsApp Bridge started on http://localhost:3001"
echo "📲 Scan the QR code above with your WhatsApp to connect"
echo ""
echo "💡 To test: curl -X POST http://localhost:8000/notifications/test"
echo "🔄 Bridge will auto-reconnect if connection is lost"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for user interrupt
trap 'echo "🛑 Stopping services..."; pkill -f "node whatsapp_bridge.js"; exit 0' INT

# Keep script running
while true; do
    sleep 1
done