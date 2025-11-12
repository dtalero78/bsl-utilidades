# Twilio-BSL Architecture Diagram

## System Overview

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    TWILIO-BSL WHATSAPP INTEGRATION                       ║
║                         (+57 315 336 9631)                               ║
╚══════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SERVICES                               │
└──────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐                           ┌─────────────────┐
    │   Twilio API    │                           │   Wix Backend   │
    │                 │                           │   (CHATBOT)     │
    │ • Send Messages │                           │ • Conversations │
    │ • Receive Msgs  │                           │ • Message Store │
    │ • Message List  │                           │ • Bot Config    │
    └────────┬────────┘                           └────────┬────────┘
             │                                              │
             │ REST API                        HTTP Functions │
             │                                              │
             ▼                                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        TWILIO_BSL.PY (Flask App)                         │
│                            Port: 5001                                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    API ENDPOINTS                               │    │
│  ├────────────────────────────────────────────────────────────────┤    │
│  │                                                                │    │
│  │  GET  /                      → Main Chat Interface (HTML)     │    │
│  │  GET  /health                → Health Check                   │    │
│  │  GET  /api/conversaciones    → Get All Conversations          │    │
│  │  GET  /api/conversacion/:id  → Get Specific Conversation      │    │
│  │  POST /api/enviar-mensaje    → Send WhatsApp Message          │    │
│  │  POST /webhook/twilio        → Receive Incoming Messages      │    │
│  │                                                                │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    CORE MODULES                                │    │
│  ├────────────────────────────────────────────────────────────────┤    │
│  │                                                                │    │
│  │  • Twilio Integration     → Send/Receive Messages             │    │
│  │  • Wix Integration        → Sync Conversations                │    │
│  │  • Message Merging        → Combine Twilio + Wix Data         │    │
│  │  • Webhook Handler        → Process Incoming Messages         │    │
│  │  • Logging                → twilio_bsl.log                    │    │
│  │                                                                │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ HTTP (Static Files + API)
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         WEB INTERFACE (Browser)                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌─────────────────────────┐  ┌─────────────────┐   │
│  │              │  │                         │  │                 │   │
│  │  Sidebar     │  │    Chat Area           │  │  Contact Info   │   │
│  │              │  │                         │  │  (Optional)     │   │
│  │ ┌──────────┐ │  │  ┌─────────────────┐   │  │                 │   │
│  │ │ Search   │ │  │  │ Contact Header  │   │  │  • Name         │   │
│  │ └──────────┘ │  │  └─────────────────┘   │  │  • Phone        │   │
│  │              │  │                         │  │  • Bot Status   │   │
│  │ Conversations│  │  ┌─────────────────┐   │  │  • Observations │   │
│  │              │  │  │                 │   │  │                 │   │
│  │ • Juan Pérez │  │  │  Messages       │   │  └─────────────────┘   │
│  │ • María G.   │  │  │                 │   │                         │
│  │ • Carlos R.  │  │  │  ┌──────────┐   │   │                         │
│  │ • Ana López  │  │  │  │ Incoming │   │   │                         │
│  │              │  │  │  └──────────┘   │   │                         │
│  │ [Refresh]    │  │  │   ┌─────────┐  │   │                         │
│  │              │  │  │   │Outgoing │  │   │                         │
│  └──────────────┘  │  │   └─────────┘  │   │                         │
│                    │  │                 │   │                         │
│                    │  │  └─────────────────┘   │                         │
│                    │  │                         │                         │
│                    │  │  ┌─────────────────┐   │                         │
│                    │  │  │  Input Area     │   │                         │
│                    │  │  │  [Type msg...] │   │                         │
│                    │  │  └─────────────────┘   │                         │
│  └──────────────┘  └─────────────────────────┘  └─────────────────┘   │
│                                                                          │
│  Technologies: HTML5, CSS3 (WhatsApp-style), Vanilla JavaScript         │
│  Features: Auto-refresh (30s), Search, Send/Receive, Real-time updates  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Sending a Message

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    USER SENDS MESSAGE FROM UI                            │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 1. User types message
                                  │    and clicks send
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        chat.js (Frontend)                                │
│  • Validate input                                                        │
│  • Format phone number                                                   │
│  • POST /api/enviar-mensaje                                              │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 2. AJAX POST request
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     twilio_bsl.py → enviar_mensaje()                     │
│  • Receive request                                                       │
│  • Validate data                                                         │
│  • Format number (add whatsapp: prefix)                                  │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ├─────────────┬────────────────────────┐
                                  │             │                        │
                                  ▼             ▼                        ▼
┌─────────────────────┐  ┌────────────────┐  ┌──────────────────────────┐
│  Twilio API         │  │  Wix CHATBOT   │  │  UI Update               │
│                     │  │                │  │                          │
│  • twilio_client    │  │  POST /guardar │  │  • Add message bubble    │
│    .messages        │  │   Conversacion │  │  • Scroll to bottom      │
│    .create()        │  │                │  │  • Clear input           │
│                     │  │  • Save to DB  │  │                          │
│  Returns: SID       │  │  • Timestamp   │  │  Optimistic rendering    │
└─────────────────────┘  └────────────────┘  └──────────────────────────┘
           │                      │                        │
           │ 3. Message sent      │ 4. Saved to Wix       │ 5. UI updated
           ▼                      ▼                        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         WhatsApp User                                    │
│  • Receives message on phone                                             │
│  • Message appears in WhatsApp app                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Receiving a Message

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    USER SENDS WHATSAPP MESSAGE                           │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 1. User sends message
                                  │    to +57 315 336 9631
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           Twilio Platform                                │
│  • Receives WhatsApp message                                             │
│  • Processes message                                                     │
│  • Calls configured webhook                                              │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 2. POST /webhook/twilio
                                  │    Form data:
                                  │    - From: whatsapp:+573001234567
                                  │    - To: whatsapp:+573153369631
                                  │    - Body: "Hola"
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    twilio_bsl.py → twilio_webhook()                      │
│  • Extract message data                                                  │
│  • Parse phone number                                                    │
│  • Log incoming message                                                  │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 3. Save to Wix
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    guardar_mensaje_en_wix()                              │
│  • Format message object                                                 │
│  • POST to Wix API                                                       │
│  • Update conversation                                                   │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 4. Success response
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         Twilio Platform                                  │
│  • Receives 200 OK                                                       │
│  • Marks message as delivered                                            │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 5. Auto-refresh (30s later)
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      Web Interface (Browser)                             │
│  • Auto-refresh timer triggers                                           │
│  • GET /api/conversacion/:numero                                         │
│  • Fetches updated messages                                              │
│  • Displays new message                                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

## Message Merging Logic

```
┌──────────────────────────────────────────────────────────────────────────┐
│              GET /api/conversacion/:numero                               │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │
                ┌─────────────────┴─────────────────┐
                │                                   │
                ▼                                   ▼
┌──────────────────────────┐          ┌──────────────────────────┐
│   Twilio Messages        │          │   Wix Messages           │
│                          │          │                          │
│  • From Twilio API       │          │  • From Wix CHATBOT      │
│  • Last 50 messages      │          │  • Collection query      │
│  • Direction: in/out     │          │  • User/system msgs      │
│  • Status: sent/delivered│          │  • Bot interactions      │
│                          │          │                          │
│  [{                      │          │  [{                      │
│    sid: "SM123...",      │          │    from: "usuario",      │
│    from: "whatsapp:+...",│          │    mensaje: "Hola",      │
│    to: "whatsapp:+...",  │          │    timestamp: "2025..." │
│    body: "Hola",         │          │  }, ...]                 │
│    date_sent: "2025...", │          │                          │
│    direction: "inbound"  │          │                          │
│  }, ...]                 │          │                          │
└──────────────────────────┘          └──────────────────────────┘
                │                                   │
                └─────────────────┬─────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    mergeMessages() Function                              │
│                                                                          │
│  1. Combine both arrays                                                  │
│  2. Normalize message format:                                            │
│     • direction: inbound/outbound                                        │
│     • body: message text                                                 │
│     • timestamp: ISO 8601                                                │
│     • status: sent/delivered/read                                        │
│  3. Remove duplicates (by content + timestamp)                           │
│  4. Sort chronologically (oldest first)                                  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      Merged Message Array                                │
│                                                                          │
│  [                                                                       │
│    { direction: "inbound",  body: "Hola", timestamp: "2025-11-12..." }, │
│    { direction: "outbound", body: "Hola!", timestamp: "2025-11-12..." },│
│    { direction: "inbound",  body: "¿Cómo estás?", ... },                │
│    ...                                                                   │
│  ]                                                                       │
│                                                                          │
│  • Complete conversation history                                         │
│  • No duplicates                                                         │
│  • Chronological order                                                   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        Render in UI                                      │
│                                                                          │
│  Inbound messages  →  Left side  (white bubble)                          │
│  Outbound messages →  Right side (green bubble)                          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## File Structure

```
/workspaces/bsl-utilidades/
│
├── twilio_bsl.py                    # Main Flask application
│   ├── Flask routes
│   ├── Twilio integration
│   ├── Wix integration
│   └── Webhook handler
│
├── templates/twilio/
│   └── chat.html                    # Main UI template
│       ├── Sidebar (conversations list)
│       ├── Chat area (messages)
│       └── Input area
│
├── static/twilio/
│   ├── css/
│   │   └── chat.css                 # WhatsApp-style CSS
│   │       ├── Layout (flex/grid)
│   │       ├── Message bubbles
│   │       ├── Colors (WhatsApp green)
│   │       └── Responsive design
│   │
│   └── js/
│       └── chat.js                  # Frontend logic
│           ├── API calls
│           ├── Message rendering
│           ├── Auto-refresh
│           └── Event handlers
│
├── test_twilio_bsl.py               # Test suite
│
├── requirements.txt                 # Dependencies
│   └── + twilio                     # Twilio SDK added
│
├── .env.example                     # Configuration template
│   ├── Twilio credentials
│   ├── Wix API config
│   └── Port settings
│
├── Procfile.twilio                  # Deployment config
│
└── Documentation/
    ├── TWILIO_BSL_README.md         # Technical docs
    ├── TWILIO_SETUP_GUIDE.md        # Setup guide
    ├── TWILIO_IMPLEMENTATION_SUMMARY.md
    └── ARCHITECTURE_DIAGRAM.md      # This file
```

## Technology Stack

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           BACKEND                                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Python 3.8+                                                             │
│  ├── Flask                  → Web framework                              │
│  ├── Flask-CORS             → Cross-origin requests                      │
│  ├── Twilio SDK             → WhatsApp API integration                   │
│  ├── Requests               → HTTP client (Wix API)                      │
│  ├── Python-dotenv          → Environment variables                      │
│  └── Logging                → Error tracking                             │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  HTML5                      → Structure                                  │
│  CSS3                       → Styling (WhatsApp theme)                   │
│  JavaScript (Vanilla)       → Logic (no frameworks)                      │
│  ├── Fetch API              → AJAX requests                              │
│  ├── DOM Manipulation       → Dynamic updates                            │
│  ├── Event Listeners        → User interactions                          │
│  └── Timers                 → Auto-refresh (setInterval)                 │
│                                                                          │
│  Font Awesome               → Icons                                      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL APIs                                     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Twilio REST API                                                         │
│  ├── Send messages          → POST /Messages                             │
│  ├── Receive messages       → Webhook                                    │
│  ├── Message history        → GET /Messages                              │
│  └── Status callbacks       → Delivery updates                           │
│                                                                          │
│  Wix HTTP Functions                                                      │
│  ├── Get conversation       → GET /obtenerConversacion                   │
│  ├── Save conversation      → POST /guardarConversacion                  │
│  └── Update observations    → POST /actualizarObservaciones              │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                        DEPLOYMENT                                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Digital Ocean App Platform                                              │
│  ├── Python buildpack                                                    │
│  ├── Port: 5001                                                          │
│  ├── Auto-deploy from Git                                                │
│  └── Environment variables                                               │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Security Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      SECURITY LAYERS                                     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Environment Variables                                                │
│     • Credentials stored in .env                                         │
│     • Never committed to Git                                             │
│     • Injected at runtime                                                │
│                                                                          │
│  2. CORS Configuration                                                   │
│     • Restrict origins                                                   │
│     • Limit methods (GET, POST only)                                     │
│                                                                          │
│  3. Input Validation                                                     │
│     • Phone number format validation                                     │
│     • Message content sanitization                                       │
│     • HTML escaping in UI                                                │
│                                                                          │
│  4. HTTPS (Production)                                                   │
│     • All traffic encrypted                                              │
│     • Digital Ocean provides SSL                                         │
│                                                                          │
│  5. Webhook Validation (Recommended)                                     │
│     • Twilio signature validation                                        │
│     • Prevent unauthorized webhook calls                                 │
│     • TODO: Implement in next version                                    │
│                                                                          │
│  6. Rate Limiting (Recommended)                                          │
│     • Prevent abuse                                                      │
│     • Protect Twilio API quota                                           │
│     • TODO: Implement in next version                                    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Deployment Architecture (Digital Ocean)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DIGITAL OCEAN                                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    App Platform                                │    │
│  │                                                                │    │
│  │  ┌──────────────────────────────────────────────────────┐     │    │
│  │  │  Container (Python 3.9)                              │     │    │
│  │  │                                                      │     │    │
│  │  │  ├─ twilio_bsl.py (running)                         │     │    │
│  │  │  ├─ Port 5001 exposed                               │     │    │
│  │  │  ├─ Environment variables injected                  │     │    │
│  │  │  └─ Logging to stdout/stderr                        │     │    │
│  │  │                                                      │     │    │
│  │  └──────────────────────────────────────────────────────┘     │    │
│  │                           │                                   │    │
│  │                           │                                   │    │
│  │                           ▼                                   │    │
│  │  ┌──────────────────────────────────────────────────────┐     │    │
│  │  │  Load Balancer (HTTPS)                               │     │    │
│  │  │  • SSL termination                                   │     │    │
│  │  │  • Health checks (/health)                           │     │    │
│  │  │  • Auto-restart on failure                           │     │    │
│  │  └──────────────────────────────────────────────────────┘     │    │
│  │                           │                                   │    │
│  └───────────────────────────┼───────────────────────────────────┘    │
│                              │                                        │
└──────────────────────────────┼────────────────────────────────────────┘
                               │
                               ▼
                    Public URL: your-app.ondigitalocean.app
                               │
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
    ┌─────────┐          ┌─────────┐          ┌─────────┐
    │ Browser │          │ Twilio  │          │   Wix   │
    │  Users  │          │ Webhook │          │   API   │
    └─────────┘          └─────────┘          └─────────┘
```

---

**Architecture Version**: 1.0.0
**Last Updated**: 2025-11-12
**Status**: Production Ready
