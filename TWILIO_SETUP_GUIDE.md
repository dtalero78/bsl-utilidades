# Twilio-BSL Quick Setup Guide

## Prerequisites

- Python 3.8+
- Twilio account with WhatsApp enabled
- Access to Wix backend functions
- Digital Ocean account (for deployment)

## Local Development Setup

### Step 1: Install Dependencies

```bash
cd /workspaces/bsl-utilidades
pip install -r requirements.txt
```

### Step 2: Configure Environment

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your credentials:
```bash
# Twilio credentials (from screenshots)
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+573153369631
TWILIO_PORT=5001

# Wix API (already configured)
WIX_BASE_URL=https://www.bsl.com.co/_functions
```

### Step 3: Test the Service

1. Start the service:
```bash
python twilio_bsl.py
```

2. You should see:
```
INFO - Starting Twilio-BSL service on port 5001
INFO - Twilio WhatsApp Number: whatsapp:+573153369631
INFO - Wix Base URL: https://www.bsl.com.co/_functions
INFO - Twilio client initialized successfully
 * Running on http://0.0.0.0:5001
```

3. Open browser and go to: `http://localhost:5001`

### Step 4: Run Tests

In a new terminal:
```bash
python test_twilio_bsl.py
```

## Production Deployment (Digital Ocean)

### Method 1: Using Digital Ocean App Platform

1. **Create New App**
   - Go to Digital Ocean Dashboard
   - Click "Create" > "Apps"
   - Connect your GitHub repository

2. **Configure Build Settings**
   - Detected: Python
   - Build command: `pip install -r requirements.txt`
   - Run command: `python twilio_bsl.py`
   - Port: `5001`

3. **Set Environment Variables**
   - Go to "Settings" > "App-Level Environment Variables"
   - Add all variables from `.env.example`
   - Important ones:
     ```
     TWILIO_ACCOUNT_SID=your_account_sid_here
     TWILIO_AUTH_TOKEN=your_auth_token_here
     TWILIO_WHATSAPP_NUMBER=whatsapp:+573153369631
     WIX_BASE_URL=https://www.bsl.com.co/_functions
     TWILIO_PORT=5001
     FLASK_DEBUG=False
     ```

4. **Deploy**
   - Click "Deploy"
   - Wait for build to complete
   - Note your app URL: `https://your-app.ondigitalocean.app`

5. **Configure Twilio Webhook**
   - Go to [Twilio Console](https://console.twilio.com/)
   - Navigate to: Messaging > WhatsApp > Senders
   - Select your number: `+57 315 336 9631`
   - Set webhook URL: `https://your-app.ondigitalocean.app/webhook/twilio`
   - Method: `POST`
   - Save

### Method 2: Using Docker (Alternative)

1. **Create Dockerfile**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5001

CMD ["python", "twilio_bsl.py"]
```

2. **Build and run**
```bash
docker build -t twilio-bsl .
docker run -p 5001:5001 --env-file .env twilio-bsl
```

## Twilio Console Configuration

### 1. Get Credentials

From your screenshots, you already have:
- **Account SID**: `your_account_sid_here`
- **Auth Token**: `your_auth_token_here`

### 2. Configure WhatsApp Sandbox (Development)

If testing with sandbox:
1. Go to: Messaging > Try it out > WhatsApp
2. Send "join [your-sandbox-code]" to the sandbox number
3. Use sandbox number for testing

### 3. Configure Production WhatsApp Number

Your production number: `+57 315 336 9631`

1. Go to: Messaging > WhatsApp > Senders
2. Click on your number
3. Under "Webhook Configuration":
   - **When a message comes in**: `https://your-app.ondigitalocean.app/webhook/twilio`
   - **Method**: POST
4. Save configuration

## Verification Steps

### 1. Check Health Endpoint

```bash
curl https://your-app.ondigitalocean.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "twilio-bsl",
  "timestamp": "2025-11-12T14:30:00.000Z",
  "twilio_configured": true
}
```

### 2. Test Webhook (with Twilio Test)

1. Go to Twilio Console
2. Navigate to your WhatsApp number
3. Click "Test" on the webhook
4. Send a test message
5. Check your logs: `twilio_bsl.log`

### 3. Send Test Message

Send a WhatsApp message to `+57 315 336 9631` and check:
- Message appears in Twilio Console
- Webhook is called (check logs)
- Message is saved to Wix CHATBOT collection

### 4. Access Web Interface

Open: `https://your-app.ondigitalocean.app/`

You should see:
- WhatsApp-style interface
- List of conversations
- Ability to click and view messages
- Message input area

## Common Issues

### Issue: "Twilio client not initialized"

**Solution**: Check that credentials are correct in `.env`
```bash
# Verify credentials are set
echo $TWILIO_ACCOUNT_SID
echo $TWILIO_AUTH_TOKEN
```

### Issue: Webhook not receiving messages

**Solution**:
1. Verify webhook URL is set in Twilio Console
2. Check URL is publicly accessible
3. Test webhook manually:
```bash
curl -X POST https://your-app.ondigitalocean.app/webhook/twilio \
  -d "From=whatsapp:+573001234567" \
  -d "To=whatsapp:+573153369631" \
  -d "Body=Test message"
```

### Issue: Messages not syncing with Wix

**Solution**:
1. Check WIX_BASE_URL is correct
2. Test Wix endpoints manually:
```bash
curl "https://www.bsl.com.co/_functions/obtenerConversacion?userId=573001234567"
```
3. Verify Wix backend is running

### Issue: Port already in use

**Solution**:
```bash
# Find process using port 5001
lsof -i :5001

# Kill the process
kill -9 <PID>

# Or use a different port
TWILIO_PORT=5002 python twilio_bsl.py
```

## Monitoring

### Check Logs

```bash
# Real-time logs
tail -f twilio_bsl.log

# Search for errors
grep ERROR twilio_bsl.log

# Search for specific phone number
grep "573001234567" twilio_bsl.log
```

### Digital Ocean Logs

If deployed on Digital Ocean:
1. Go to your app in the dashboard
2. Click "Runtime Logs"
3. View real-time logs

### Twilio Logs

1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to: Monitor > Logs > Messaging
3. Filter by your WhatsApp number

## Security Checklist

- [ ] Twilio Auth Token is kept secret
- [ ] `.env` file is not committed to git
- [ ] HTTPS is enabled in production
- [ ] Webhook URL uses HTTPS
- [ ] Consider adding authentication to web interface
- [ ] Rate limiting is configured (if needed)
- [ ] Firewall rules are set (if needed)

## Performance Optimization

### For high message volume:

1. **Increase auto-refresh interval**
   - Edit `static/twilio/js/chat.js`
   - Change `30000` (30 seconds) to higher value

2. **Add caching**
   - Consider Redis for conversation caching
   - Reduce Wix API calls

3. **Use WebSockets**
   - Replace polling with real-time updates
   - Better user experience

## Next Steps

1. ✅ Service is running
2. ✅ Webhook is configured
3. ✅ Messages are syncing
4. 🔄 Test sending/receiving messages
5. 🔄 Add authentication if needed
6. 🔄 Monitor for 24 hours
7. 🔄 Set up alerts for errors

## Support

If you encounter issues:

1. Check logs: `twilio_bsl.log`
2. Test endpoints with curl
3. Verify Twilio Console configuration
4. Check Wix endpoints are accessible
5. Review this guide again

## Quick Reference

### Service Commands

```bash
# Start service
python twilio_bsl.py

# Start with custom port
TWILIO_PORT=5002 python twilio_bsl.py

# Run tests
python test_twilio_bsl.py

# View logs
tail -f twilio_bsl.log
```

### Important URLs

- **Local Interface**: http://localhost:5001
- **Production Interface**: https://your-app.ondigitalocean.app
- **Health Check**: /health
- **API Docs**: See TWILIO_BSL_README.md
- **Twilio Console**: https://console.twilio.com/
- **Wix Functions**: https://www.bsl.com.co/_functions

### Key Files

- `twilio_bsl.py` - Main application
- `templates/twilio/chat.html` - Web interface
- `static/twilio/css/chat.css` - Styles
- `static/twilio/js/chat.js` - Frontend logic
- `.env` - Configuration
- `twilio_bsl.log` - Logs

---

**Ready to go!** 🚀

Your Twilio-BSL WhatsApp integration is now set up and ready to use.
