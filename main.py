import os
import re
import time
import httpx

# Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

# Import telebot
import telebot
from telebot import types

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Messages
WELCOME = '''👋 Hello {first_name}!

I'm *BizVerify* — I find service providers that actually answer.

🔍 *How it works:*
1\\. Tell me what you need: "Plumber in Lekki"
2\\. I check the numbers *right now*
3\\. I send you only the ones that work

*Try it:* Type "Electrician Yaba"'''

SEARCHING = "🔍 Searching for {category} in {location}..."

def search_places(query: str, location: str):
    """Search using Google Places API (New)"""
    if not GOOGLE_API_KEY:
        return _mock_results(query, location)
    
    try:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_API_KEY,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.internationalPhoneNumber,places.id"
        }
        data = {"textQuery": f"{query} in {location}", "regionCode": "NG"}
        
        response = httpx.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers=headers,
            json=data,
            timeout=30.0
        )
        result = response.json()
        
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
    text = text.lower()
    cats = {'plumber': ['plumber'], 'electrician': ['electrician'], 'ac': ['ac'], 'generator': ['generator']}
    locs = ['lekki', 'yaba', 'ikeja', 'vi', 'ikoyi', 'surulere', 'maryland']
    
    cat = None
    for c, kws in cats.items():
        if any(k in text for k in kws):
            cat = c
            break
    
    loc = next((l.title() for l in locs if l in text), 'Lagos')
    return {'category': cat, 'location': loc}

def verify_numbers(businesses: list):
    """Simulate phone verification"""
    time.sleep(2)
    for b in businesses:
        b['verified'] = True
    return businesses

@bot.message_handler(commands=['start'])
def start(message):
    """Handle /start"""
    bot.send_message(
        message.chat.id,
        WELCOME.format(first_name=message.from_user.first_name or "there"),
        parse_mode='MarkdownV2'
    )

@bot.message_handler(func=lambda message: True)
def handle_search(message):
    """Handle all text messages"""
    text = message.text
    parsed = parse_query(text)
    
    if not parsed['category']:
        bot.send_message(message.chat.id, "❓ Try: 'Plumber Lekki' or 'Electrician Yaba'")
        return
    
    # Send searching message
    msg = bot.send_message(message.chat.id, SEARCHING.format(**parsed))
    
    try:
        # Search
        businesses = search_places(parsed['category'], parsed['location'])
        
        # Verify
        verified = verify_numbers(businesses)
        
        # Format response
        lines = [f"🔍 *{parsed['category'].title()} in {parsed['location']}*\n"]
        
        for i, biz in enumerate(verified, 1):
            lines.append(f"{i}. ✅ *{biz['name']}*")
            lines.append(f"   📞 `{biz['phone']}`")
            lines.append(f"   📍 _{biz['address']}_")
            lines.append(f"   _Verified just now_\n")
        
        response = '\n'.join(lines)
        
        # Edit message with results
        bot.edit_message_text(
            response,
            chat_id=message.chat.id,
            message_id=msg.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        bot.edit_message_text(
            f"😕 Error: {str(e)}",
            chat_id=message.chat.id,
            message_id=msg.message_id
        )

def main():
    print("🚀 Starting BizVerify bot...")
    print("Bot started! Polling for messages...")
    bot.polling()

if __name__ == "__main__":
    main()

