# Twilio-BSL WhatsApp Chat Integration

## Overview

This is a completely independent endpoint for managing WhatsApp conversations via Twilio, designed to integrate with the existing Wix CHATBOT collection. The system provides a WhatsApp Web-style interface for managing all conversations associated with the BSL WhatsApp line (+57 315 336 9631).

## Features

### Core Functionality
- ✅ **WhatsApp-style chat interface** - Modern, responsive design matching WhatsApp Web
- ✅ **Real-time message sending/receiving** - Direct integration with Twilio API
- ✅ **Wix CHATBOT sync** - Automatic synchronization with existing Wix conversation storage
- ✅ **Webhook support** - Receives incoming messages from Twilio
- ✅ **Multi-conversation management** - Handle multiple simultaneous conversations
- ✅ **Auto-refresh** - Conversations update automatically every 30 seconds

### Key Features
- 📱 View all conversations for the configured WhatsApp number
- 💬 Send and receive messages in real-time
- 🔄 Automatic sync with Wix CHATBOT collection
- 🤖 Integration with existing Wix bot messages
- 📊 Conversation history from both Twilio and Wix sources
- 🔍 Search conversations by name or phone number
- 👤 Contact information panel with Wix data

## Architecture

### Independent Service
The Twilio-BSL endpoint (`twilio_bsl.py`) runs as a completely separate Flask application from the main `descargar_bsl.py` service:

- **Main App**: `descargar_bsl.py` (port 8080) - PDF generation and medical certificates
- **Twilio-BSL**: `twilio_bsl.py` (port 5001) - WhatsApp chat interface

This separation ensures:
- No conflicts with existing services
- Independent scaling and deployment
- Isolated error handling
- Clear separation of concerns

### Technology Stack
- **Backend**: Python Flask
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **APIs**: Twilio REST API, Wix HTTP Functions
- **Storage**: Wix CHATBOT collection (via exposed endpoints)

### Data Flow

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Twilio    │ ◄─────► │  twilio_bsl  │ ◄─────► │  Wix API    │
│  WhatsApp   │  REST   │   (Flask)    │   HTTP  │  (CHATBOT)  │
└─────────────┘         └──────────────┘         └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │   Browser    │
                        │ Chat Interface│
                        └──────────────┘
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` now includes:
- `twilio` - Twilio Python SDK

### 2. Configure Environment Variables

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
```

Edit `.env` and set the following variables:

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+573153369631
TWILIO_PORT=5001

# Wix Integration
WIX_BASE_URL=https://www.bsl.com.co/_functions
WIX_API_KEY=  # Optional, if needed for authentication
```

### 3. Run the Service

```bash
python twilio_bsl.py
```

The service will start on `http://localhost:5001`

### 4. Access the Interface

Open your browser and navigate to:
```
http://localhost:5001
```

## API Endpoints

### GET /
Main chat interface (HTML)

### GET /api/conversaciones
Get all conversations grouped by phone number

**Response:**
```json
{
  "success": true,
  "conversaciones": {
    "573001234567": {
      "twilio_messages": [...],
      "wix_data": {...},
      "numero": "573001234567",
      "nombre": "Juan Pérez",
      "stopBot": false,
      "observaciones": ""
    }
  },
  "total": 5
}
```

### GET /api/conversacion/<numero>
Get specific conversation by phone number

**Response:**
```json
{
  "success": true,
  "numero": "573001234567",
  "wix_data": {
    "mensajes": [...],
    "stopBot": false,
    "observaciones": ""
  },
  "twilio_messages": [...]
}
```

### POST /api/enviar-mensaje
Send WhatsApp message via Twilio

**Request:**
```json
{
  "to": "+573001234567",
  "message": "Hola, ¿cómo estás?",
  "media_url": "https://..." // Optional
}
```

**Response:**
```json
{
  "success": true,
  "message_sid": "SM1234567890abcdef",
  "timestamp": "2025-11-12T14:30:00.000Z"
}
```

### POST /webhook/twilio
Webhook endpoint for Twilio incoming messages

**Configuration**: Set this URL in your Twilio console:
```
https://your-domain.com/webhook/twilio
```

### GET /health
Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "service": "twilio-bsl",
  "timestamp": "2025-11-12T14:30:00.000Z",
  "twilio_configured": true
}
```

## Wix Integration

### CHATBOT Collection Structure

The system integrates with the following Wix endpoints (defined in `funcionesWix/http.js` and `funcionesWix/expose.js`):

#### GET /obtenerConversacion
Fetch conversation for specific phone number

**Parameters:**
- `userId`: Phone number (without + or whatsapp: prefix)

**Response:**
```json
{
  "mensajes": [
    {
      "from": "usuario",
      "mensaje": "Hola",
      "timestamp": "2025-11-12T14:30:00.000Z"
    }
  ],
  "stopBot": false,
  "observaciones": "",
  "threadId": ""
}
```

#### POST /guardarConversacion
Save message to Wix CHATBOT collection

**Request:**
```json
{
  "userId": "573001234567",
  "nombre": "Juan Pérez",
  "mensajes": [{
    "from": "sistema",
    "mensaje": "Hola",
    "timestamp": "2025-11-12T14:30:00.000Z"
  }],
  "threadId": "",
  "ultimoMensajeBot": ""
}
```

### Message Synchronization

The system automatically:
1. **Fetches** conversation history from both Twilio and Wix
2. **Merges** messages from both sources chronologically
3. **Saves** new outgoing messages to both Twilio (via API) and Wix (via HTTP endpoint)
4. **Receives** incoming messages via Twilio webhook and saves to Wix

## Twilio Configuration

### 1. Twilio Console Setup

1. Log in to [Twilio Console](https://console.twilio.com/)
2. Navigate to **WhatsApp > Senders**
3. Note your WhatsApp number: `+57 315 336 9631`
4. Copy your **Account SID** and **Auth Token**

### 2. Configure Webhook

Set the incoming message webhook URL in Twilio console:

**When a message comes in:**
```
https://your-domain.com/webhook/twilio
```

**Method:** POST

### 3. WhatsApp Number Format

Twilio uses the format: `whatsapp:+573153369631`

The system automatically handles:
- Adding the `whatsapp:` prefix when sending
- Removing it for storage and display
- Formatting for user-friendly display: `+57 315 336 9631`

## Deployment

### Digital Ocean App Platform

1. **Create new app** in Digital Ocean
2. **Connect repository** containing this code
3. **Configure build**:
   - Build command: `pip install -r requirements.txt`
   - Run command: `python twilio_bsl.py`
4. **Set environment variables** (see .env.example)
5. **Configure port**: 5001
6. **Deploy**

### Environment Variables for Production

Set these in your Digital Ocean app settings:

```bash
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+573153369631
WIX_BASE_URL=https://www.bsl.com.co/_functions
TWILIO_PORT=5001
FLASK_DEBUG=False
```

### Update Twilio Webhook

Once deployed, update the Twilio webhook URL to:
```
https://your-app.ondigitalocean.app/webhook/twilio
```

## Usage Guide

### Viewing Conversations

1. Open the chat interface in your browser
2. Conversations are listed in the left sidebar
3. Click on any conversation to view messages
4. Messages are sorted chronologically, merging Twilio and Wix sources

### Sending Messages

1. Select a conversation from the sidebar
2. Type your message in the input field at the bottom
3. Press Enter or click the send button
4. Message is sent via Twilio and saved to Wix

### Receiving Messages

Incoming messages are:
1. Received by Twilio webhook
2. Automatically saved to Wix CHATBOT collection
3. Displayed in the chat interface on next refresh (30 seconds)

### Search Conversations

Use the search box at the top of the sidebar to filter conversations by:
- Contact name
- Phone number

### Auto-Refresh

The interface automatically refreshes:
- All conversations every 30 seconds (when no conversation is open)
- Current conversation every 30 seconds (when a conversation is open)

Manual refresh available via the refresh button in the sidebar header.

## User Interface

### WhatsApp-Style Design

The interface closely matches WhatsApp Web:

- **Green color scheme** - WhatsApp brand colors
- **Three-column layout** - Conversations list, chat area, contact info (optional)
- **Message bubbles** - Different styles for incoming/outgoing
- **Timestamps** - Smart time formatting (today: HH:MM, yesterday: "Ayer", older: DD/MM)
- **Status indicators** - Single/double checkmarks for message delivery
- **Typing area** - Auto-expanding textarea, emoji support ready

### Responsive Design

The interface adapts to different screen sizes:
- **Desktop**: Three-column layout with all features
- **Tablet**: Two-column layout (hide contact info)
- **Mobile**: Single column with conversation/chat toggle

## Error Handling

### Connection Errors
- Automatic retry for failed API calls
- User-friendly error messages
- Graceful degradation when Twilio is unavailable

### Message Failures
- Failed messages are indicated with error status
- Retry mechanism for sending
- Logging of all errors to `twilio_bsl.log`

### Wix Sync Failures
- Continue to work with Twilio even if Wix is unavailable
- Retry sync on next successful operation
- Log sync issues for debugging

## Logging

All operations are logged to `twilio_bsl.log`:

```python
2025-11-12 14:30:00 - INFO - Twilio client initialized successfully
2025-11-12 14:30:15 - INFO - Fetching conversation for 573001234567
2025-11-12 14:30:16 - INFO - Message sent successfully. SID: SM1234567890abcdef
2025-11-12 14:30:20 - INFO - Incoming message from whatsapp:+573001234567: Hola
```

## Security Considerations

### Authentication
- Consider adding authentication layer for production
- Restrict access to authorized users only
- Use HTTPS in production

### API Keys
- Never commit `.env` file to version control
- Use environment variables for all credentials
- Rotate Twilio Auth Token periodically

### Webhook Security
- Validate Twilio webhook signatures (to be implemented)
- Use HTTPS for webhook URLs
- Implement rate limiting

## Troubleshooting

### Messages not sending
1. Check Twilio credentials in `.env`
2. Verify WhatsApp number format
3. Check Twilio console for account status
4. Review logs in `twilio_bsl.log`

### Conversations not loading
1. Check Wix API endpoint availability
2. Verify WIX_BASE_URL in `.env`
3. Test Wix endpoints manually
4. Check network connectivity

### Webhook not receiving messages
1. Verify webhook URL in Twilio console
2. Check that endpoint is publicly accessible
3. Review Twilio webhook logs
4. Test webhook manually with curl

## Future Enhancements

### Planned Features
- [ ] User authentication and roles
- [ ] Media message support (images, documents)
- [ ] Message templates
- [ ] Broadcast messages to multiple contacts
- [ ] Analytics dashboard
- [ ] Message search
- [ ] Contact management
- [ ] Tag/label system for conversations
- [ ] Automated responses
- [ ] Integration with other communication channels

### Technical Improvements
- [ ] WebSocket support for real-time updates (replace polling)
- [ ] Message queue for reliable delivery
- [ ] Database for conversation caching
- [ ] Redis for session management
- [ ] Twilio webhook signature validation
- [ ] Rate limiting and throttling
- [ ] Comprehensive unit tests
- [ ] Performance monitoring

## File Structure

```
/workspaces/bsl-utilidades/
├── twilio_bsl.py                   # Main Flask application
├── templates/twilio/
│   └── chat.html                   # Chat interface template
├── static/twilio/
│   ├── css/
│   │   └── chat.css                # WhatsApp-style CSS
│   └── js/
│       └── chat.js                 # Chat functionality JavaScript
├── funcionesWix/
│   ├── http.js                     # Wix HTTP endpoints (reference)
│   └── expose.js                   # Wix database functions (reference)
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variables template
├── .env                            # Your environment variables (git-ignored)
└── twilio_bsl.log                  # Application logs
```

## Support

For issues or questions:
1. Check the logs in `twilio_bsl.log`
2. Review this documentation
3. Test endpoints manually with curl
4. Contact the development team

## License

This software is proprietary to BSL Medicina Ocupacional.

---

**Version:** 1.0.0
**Last Updated:** 2025-11-12
**Author:** Claude Code Assistant
