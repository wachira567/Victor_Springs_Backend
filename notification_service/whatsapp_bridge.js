const {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
} = require("@whiskeysockets/baileys");
const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const qrcode = require("qrcode-terminal");
const bodyParser = require("body-parser");
const fs = require("fs");

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: ["http://localhost:5173", "http://localhost:3000", "*"],
    methods: ["GET", "POST"],
  },
});
app.use(bodyParser.json());

// Store mapping: WhatsApp Message ID -> Web Socket ID
// We need this to know who sent the original message you are quoting
let messageMap = {};
let adminPhone = process.env.ADMIN_WHATSAPP_NUMBER
  ? (process.env.ADMIN_WHATSAPP_NUMBER.startsWith("+")
      ? process.env.ADMIN_WHATSAPP_NUMBER.slice(1)
      : process.env.ADMIN_WHATSAPP_NUMBER) + "@s.whatsapp.net"
  : "254754096684@s.whatsapp.net"; // Default fallback

async function startWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState("auth_info");

  const sock = makeWASocket({
    auth: state,
    printQRInTerminal: true, // This will show the QR code in your terminal
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      console.log("🔗 Scan this QR code with WhatsApp:");
      qrcode.generate(qr, { small: true });
    }
    if (connection === "close") {
      const shouldReconnect =
        lastDisconnect.error?.output?.statusCode !== DisconnectReason.loggedOut;
      console.log("Connection closed. Reconnecting...", shouldReconnect);
      if (shouldReconnect) startWhatsApp();
    } else if (connection === "open") {
      console.log("✅ WhatsApp Connected to Victor Springs!");
    }
  });

  // API Endpoint: Python backend calls this to send WhatsApp messages
  app.post("/send-whatsapp", async (req, res) => {
    const { phone, message } = req.body;

    // Convert local 07... to 2547... format
    const formattedPhone = phone.startsWith("0")
      ? "254" + phone.slice(1)
      : phone.startsWith("+")
      ? phone.slice(1)
      : phone;

    const id = formattedPhone + "@s.whatsapp.net";

    try {
      await sock.sendMessage(id, { text: message });
      console.log(`📱 WhatsApp sent to ${phone}`);
      res.json({ status: "success", method: "whatsapp" });
    } catch (error) {
      console.error("WhatsApp Error:", error);
      res.status(500).json({
        status: "error",
        method: "whatsapp",
        error: error.message,
      });
    }
  });

  // Health check endpoint
  app.get("/health", (req, res) => {
    res.json({
      status: "ok",
      service: "Victor Springs WhatsApp Bridge",
      timestamp: new Date().toISOString(),
      active_connections: io.sockets.sockets.size,
      mapped_messages: Object.keys(messageMap).length,
    });
  });

  // 1. LISTEN: Admin replies to a message (using quoted replies)
  sock.ev.on("messages.upsert", async (m) => {
    const msg = m.messages[0];

    // Check if it's a text message from YOU (Admin)
    if (!msg.key.fromMe && msg.key.remoteJid === adminPhone) {
      // Check if you QUOTED a message (Swiped right)
      const contextInfo = msg.message?.extendedTextMessage?.contextInfo;
      const quoteId = contextInfo?.stanzaId; // The ID of the message you quoted

      if (quoteId && messageMap[quoteId]) {
        const targetSocketId = messageMap[quoteId];
        const replyText =
          msg.message.conversation ||
          msg.message.extendedTextMessage?.text ||
          "";

        // Send back to the specific website user
        io.to(targetSocketId).emit("receive_message", {
          text: replyText,
          from: "Admin",
        });
        console.log(`↩️ Replied to User via Quote ID: ${quoteId}`);
      } else {
        console.log(
          "⚠️ You replied, but didn't quote a specific user message."
        );
      }
    }
  });

  // 2. SEND: Website User -> WhatsApp Admin
  io.on("connection", (socket) => {
    console.log("🌐 Web User Connected:", socket.id);

    socket.on("send_message", async (data) => {
      try {
        // Send to Admin WhatsApp
        const sentMsg = await sock.sendMessage(adminPhone, {
          text: `👤 *New Website Guest*\n${data.text}`,
        });

        // SAVE the Message ID so we can track it later when you quote it
        // sentMsg.key.id is the unique ID WhatsApp assigns to this specific bubble
        messageMap[sentMsg.key.id] = socket.id;
        console.log(`📤 Message sent to admin, mapped ID: ${sentMsg.key.id}`);
      } catch (error) {
        console.error("❌ Failed to send message to admin:", error);
        socket.emit("error", {
          message: "Failed to send message. Please try again.",
        });
      }
    });

    socket.on("disconnect", () => {
      console.log("🌐 Web User Disconnected:", socket.id);
      // Clean up message mappings for this socket
      Object.keys(messageMap).forEach((key) => {
        if (messageMap[key] === socket.id) {
          delete messageMap[key];
        }
      });
    });
  });
}

startWhatsApp();

const PORT = process.env.WHATSAPP_BRIDGE_PORT || 3001;
server.listen(PORT, () => {
  console.log(
    `🚀 Victor Springs WhatsApp Bridge running on http://localhost:${PORT}`
  );
  console.log(`💬 Chat widget support enabled`);
});
