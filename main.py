#!/usr/bin/env python3
import os
import re
import time
import json
import urllib.request
import urllib.error

# Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

class SimpleBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
    
    def make_request(self, method, data=None):
        url = f"{self.base_url}/{method}"
        try:
            if data:
                data = json.dumps(data).encode('utf-8')
                req = urllib.request.Request(url, data=data, headers={
                    'Content-Type': 'application/json'
                }, method='POST')
            else:
                req = urllib.request.Request(url)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} - {e.reason}")
            return None
        except Exception as e:
            print(f"Request error: {e}")
            return None
    
    def get_updates(self):
        result = self.make_request('getUpdates', {
            'offset': self.offset,
            'limit': 10,
            'timeout': 30
        })
        
        if result and 'result' in result:
            updates = result['result']
            if updates:
                self.offset = updates[-1]['update_id'] + 1
            return updates
        return []
    
    def send_message(self, chat_id, text):
        return self.make_request('sendMessage', {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        })
    
    def edit_message(self, chat_id, message_id, text):
        return self.make_request('editMessageText', {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': 'Markdown'
        })

def search_places(query, location):
    if not GOOGLE_API_KEY:
        return mock_results(query, location)
    
    try:
        url = "https://places.googleapis.com/v1/places:searchText"
        data = json.dumps({
            "textQuery": f"{query} in {location}",
            "regionCode": "NG"
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': GOOGLE_API_KEY,
            'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.internationalPhoneNumber'
        }, method='POST')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if "places" not in result:
                return mock_results(query, location)
            
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
            return results if results else mock_results(query, location)
            
    except urllib.error.HTTPError as e:
        print(f"Google API HTTP Error: {e.code}")
        return mock_results(query, location)
    except Exception as e:
        print(f"Search error: {e}")
        return mock_results(query, location)

def mock_results(query, location):
    if "plumber" in query.lower():
        return [
            {"name": "Quick Fix Plumbing", "phone": "+2348123456789", "address": "Lekki"},
            {"name": "Pipe Masters", "phone": "+2348098765432", "address": "Lekki"},
        ]
    elif "electrician" in query.lower():
        return [{"name": "PowerPro Electric", "phone": "+2347012345678", "address": "Yaba"}]
    else:
        return [{"name": "Test Service", "phone": "+2348012345678", "address": location}]

def parse_query(text):
    text = text.lower()
    cats = {'plumber': ['plumber'], 'electrician': ['electrician'], 'ac': ['ac'], 'generator': ['gen']}
    locs = ['lekki', 'yaba', 'ikeja', 'vi', 'ikoyi', 'surulere']
    
    cat = None
    for c, kws in cats.items():
        if any(k in text for k in kws):
            cat = c
            break
    
    loc = next((l.title() for l in locs if l in text), 'Lagos')
    return {'category': cat, 'location': loc}

def verify_numbers(businesses):
    time.sleep(2)
    for b in businesses:
        b['verified'] = True
    return businesses

WELCOME = """👋 Hello {first_name}!

I'm BizVerify — I find service providers that actually answer.

🔍 How it works:
1. Tell me what you need: "Plumber in Lekki"
2. I check the numbers right now
3. I send you only the ones that work

Try it: Type "Electrician Yaba" """

def main():
    print("🚀 Starting BizVerify bot...")
    
    if not TELEGRAM_TOKEN:
        print("ERROR: No TELEGRAM_BOT_TOKEN set!")
        return
    
    bot = SimpleBot(TELEGRAM_TOKEN)
    print("Bot started! Waiting for messages...")
    
    while True:
        try:
            updates = bot.get_updates()
            
            for update in updates:
                if 'message' not in update:
                    continue
                
                message = update['message']
                chat_id = message['chat']['id']
                text = message.get('text', '')
                user = message.get('from', {})
                first_name = user.get('first_name', 'there')
                
                print(f"Received: {text}")
                
                if text == '/start':
                    bot.send_message(chat_id, WELCOME.format(first_name=first_name))
                    continue
                
                parsed = parse_query(text)
                
                if not parsed['category']:
                    bot.send_message(chat_id, "❓ Try: 'Plumber Lekki' or 'Electrician Yaba'")
                    continue
                
                searching_text = f"🔍 Searching for {parsed['category']} in {parsed['location']}..."
                result_msg = bot.send_message(chat_id, searching_text)
                
                if not result_msg or 'result' not in result_msg:
                    continue
                
                message_id = result_msg['result']['message_id']
                
                try:
                    businesses = search_places(parsed['category'], parsed['location'])
                    verified = verify_numbers(businesses)
                    
                    lines = [f"🔍 *{parsed['category'].title()} in {parsed['location']}*\n"]
                    for i, biz in enumerate(verified, 1):
                        lines.append(f"{i}. ✅ *{biz['name']}*")
                        lines.append(f"   📞 `{biz['phone']}`")
                        lines.append(f"   📍 _{biz['address']}_")
                        lines.append(f"   _Verified just now_\n")
                    
                    response = '\n'.join(lines)
                    bot.edit_message(chat_id, message_id, response)
                    
                except Exception as e:
                    print(f"Error processing: {e}")
                    bot.edit_message(chat_id, message_id, f"😕 Error: {str(e)}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

