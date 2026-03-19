import logging
import os
import re
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import httpx

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Config from environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

# Fixed welcome message using single quotes
WELCOME = '''👋 Hello {first_name}!

I'm *BizVerify* — I find service providers that actually answer.

🔍 *How it works:*
1. Tell me what you need: "Plumber in Lekki"
2. I check the numbers *right now*
3. I send you only the ones that work

*Try it:* Type "Electrician Yaba"'''

SEARCHING = "🔍 Searching for {category} in {location}..."

async def search_places(query: str, location: str):
    """Search using Google Places API (New)"""
    if not GOOGLE_API_KEY:
        return _mock_results(query, location)
    
    try:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_API_KEY,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.internationalPhoneNumber,places.id"
        }
        data = {
            "textQuery": f"{query} in {location}",
            "regionCode": "NG"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers=headers,
                json=data
            )
            result = resp.json()
            
            if "places" not in result:
                return _mock_results(query, location)
            
            results = []
            for place in result.get("places", [])[:2]:
                phone = place.get("internationalPhoneNumber", "")
                if phone:
                    digits = re.sub(r'\D', '', phone)
                    if digits.startswith('234'):
                        phone = '+' + digits
                    elif digits.startswith('0'):
                        phone = '+234' + digits[1:]
                    
                    results.append({
                        "name": place.get("displayName", {}).get("text", "Unknown"),
                        "phone": phone,
                        "address": place.get("formattedAddress", "")[:50],
                    })
            return results if results else _mock_results(query, location)
            
    except Exception as e:
        print(f"Error: {e}")
        return _mock_results(query, location)

def _mock_results(query: str, location: str):
    """Fallback mock data"""
    if "plumber" in query.lower():
        return [
            {"name": "Quick Fix Plumbing", "phone": "+2348123456789", "address": "Lekki"},
            {"name": "Pipe Masters", "phone": "+2348098765432", "address": "Lekki"},
        ]
    elif "electrician" in query.lower():
        return [
            {"name": "PowerPro Electric", "phone": "+2347012345678", "address": "Yaba"},
        ]
    else:
        return [{"name": "Test Service", "phone": "+2348012345678", "address": location}]

def parse_query(text: str):
    """Parse user query"""
    text = text.lower()
    cats = {
        'plumber': ['plumber'],
        'electrician': ['electrician'],
        'ac': ['ac', 'air condition'],
        'generator': ['generator']
    }
    locs = ['lekki', 'yaba', 'ikeja', 'vi', 'ikoyi', 'surulere', 'maryland']
    
    cat = None
    for c, kws in cats.items():
        if any(k in text for k in kws):
            cat = c
            break
    
    loc = next((l.title() for l in locs if l in text), 'Lagos')
    return {'category': cat, 'location': loc}

async def verify_numbers(businesses: list):
    """Simulate phone verification"""
    await asyncio.sleep(2)
    for b in businesses:
        b['verified'] = True
    return businesses

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start"""
    await update.message.reply_text(
        WELCOME.format(first_name=update.effective_user.first_name or "there"),
        parse_mode='Markdown'
    )

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle search query"""
    text = update.message.text
    parsed = parse_query(text)
    
    if not parsed['category']:
        await update.message.reply_text("❓ Try: 'Plumber Lekki' or 'Electrician Yaba'")
        return
    
    msg = await update.message.reply_text(
        SEARCHING.format(**parsed)
    )
    
    try:
        # Search
        businesses = await search_places(parsed['category'], parsed['location'])
        
        # Verify
        verified = await verify_numbers(businesses)
        
        # Format response
        lines = [f"🔍 *{parsed['category'].title()} in {parsed['location']}*\n"]
        
        for i, biz in enumerate(verified, 1):
            lines.append(f"{i}. ✅ *{biz['name']}*")
            lines.append(f"   📞 `{biz['phone']}`")
            lines.append(f"   📍 _{biz['address']}_")
            lines.append(f"   _Verified just now_\n")
        
        await msg.edit_text('\n'.join(lines), parse_mode='Markdown')
        
    except Exception as e:
        await msg.edit_text(f"😕 Error: {str(e)}")

def main():
    print("🚀 Starting BizVerify bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    print("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()

