#!/usr/bin/env python3
import os
import re
import time
import json
import urllib.request
import urllib.error
import urllib.parse
import sqlite3
import threading
from datetime import datetime
from flask import Flask

# ============================================
# CONFIG - Environment Variables
# ============================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")  # Optional now

# Flask app for Render
app = Flask(__name__)

@app.route('/')
def health():
    return "BizVerify Bot is running!", 200

# ============================================
# ANALYTICS DATABASE - Tracks user behavior
# ============================================
def init_analytics_db():
    """
    Creates a simple database to track:
    - Who is using the bot (user_id)
    - What they search for (query, location)
    - How many results they get
    - When they searched (timestamp)
    - How many times they came back (retention)
    """
    conn = sqlite3.connect('analytics.db')
    c = conn.cursor()
    
    # Tracks every search made
    c.execute('''CREATE TABLE IF NOT EXISTS searches
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id TEXT, 
                  query TEXT, 
                  location TEXT, 
                  results_count INTEGER, 
                  timestamp TEXT)''')
    
    # Tracks unique users and their retention
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY, 
                  first_search TEXT, 
                  last_search TEXT, 
                  total_searches INTEGER DEFAULT 1,
                  username TEXT)''')
    
    conn.commit()
    conn.close()

def track_search(user_id, username, query, location, results_count):
    """
    Call this every time someone searches
    Tracks: Who searched, what they searched, when, how many results
    """
    try:
        conn = sqlite3.connect('analytics.db')
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        # Log this specific search
        c.execute("INSERT INTO searches (user_id, query, location, results_count, timestamp) VALUES (?, ?, ?, ?, ?)",
                  (str(user_id), query, location, results_count, now))
        
        # Update or create user record (for retention tracking)
        c.execute('''INSERT INTO users (user_id, username, first_search, last_search, total_searches)
                     VALUES (?, ?, ?, ?, 1)
                     ON CONFLICT(user_id) DO UPDATE SET
                     last_search = excluded.last_search,
                     total_searches = users.total_searches + 1''',
                  (str(user_id), username or "Unknown", now, now))
        
        conn.commit()
        conn.close()
        print(f"📊 Tracked search: {query} in {location} by {user_id}")
    except Exception as e:
        print(f"Analytics error (non-critical): {e}")

def get_analytics_summary():
    """
    Shows you how the bot is performing
    Run this manually to check stats
    """
    try:
        conn = sqlite3.connect('analytics.db')
        c = conn.cursor()
        
        # Total searches
        c.execute("SELECT COUNT(*) FROM searches")
        total_searches = c.fetchone()[0]
        
        # Unique users
        c.execute("SELECT COUNT(*) FROM users")
        unique_users = c.fetchone()[0]
        
        # Users who searched more than once (retention)
        c.execute("SELECT COUNT(*) FROM users WHERE total_searches > 1")
        returning_users = c.fetchone()[0]
        
        # Top searches
        c.execute("SELECT query, COUNT(*) as count FROM searches GROUP BY query ORDER BY count DESC LIMIT 5")
        top_searches = c.fetchall()
        
        conn.close()
        
        return {
            "total_searches": total_searches,
            "unique_users": unique_users,
            "returning_users": returning_users,
            "retention_rate": f"{(returning_users/max(unique_users,1))*100:.1f}%",
            "top_searches": top_searches
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================
# TELEGRAM BOT CLASS
# ============================================
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

# ============================================
# OSM SEARCH - Free, No API Key Needed
# ============================================
def search_places_osm(query, location):
    """
    Search OpenStreetMap for businesses in Nigeria
    FREE - No registration, no API key, unlimited requests
    """
    # Map what users type to OSM categories
    category_map = {
        'plumber': ['"craft"="plumber"', '"shop"="plumbing"'],
        'electrician': ['"craft"="electrician"', '"shop"="electrical"'],
        'ac': ['"repair"="air_conditioning"', '"shop"="hvac"'],
        'generator': ['"repair"="generator"', '"shop"="electrical"'],
        'tailor': ['"craft"="tailor"'],
        'mechanic': ['"craft"="mechanic"', '"shop"="car_repair"'],
        'carpenter': ['"craft"="carpenter"'],
        'painter': ['"craft"="painter"'],
        'cleaner': ['"service"="cleaning"'],
        'driver': ['"service"="taxi"', '"service"="driver"']
    }
    
    # Default to general repair if category not found
    tags = category_map.get(query.lower(), ['"shop"="yes"', '"craft"="yes"'])
    
    # Build the search query for OSM
    tag_query = '|'.join(tags)
    
    # Nigeria area (approximate coordinates)
    # Format: (south, west, north, east)
    nigeria_area = "2.7,4.2,14.7,13.9"
    
    # Overpass API query language
    overpass_query = f"""
    [out:json][timeout:25];
    (
      node[{tag_query}]({nigeria_area});
      way[{tag_query}]({nigeria_area});
    );
    out body;
    >;
    out skel qt;
    """
    
    try:
        print(f"🔍 Searching OSM for {query} in {location}...")
        url = "https://overpass-api.de/api/interpreter"
        data = urllib.parse.urlencode({'data': overpass_query}).encode()
        
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            businesses = []
            for element in result.get('elements', []):
                if 'tags' not in element:
                    continue
                
                tags_data = element['tags']
                name = tags_data.get('name', tags_data.get('brand', ''))
                
                # Skip if no name
                if not name or name.strip() == '':
                    continue
                
                # Get phone number (OSM uses different tags)
                phone = (tags_data.get('phone') or 
                        tags_data.get('contact:phone') or 
                        tags_data.get('mobile') or
                        tags_data.get('telephone'))
                
                if not phone:
                    continue  # Skip businesses without phone numbers
                
                # Clean and format phone
                phone = format_nigerian_phone(phone)
                if not phone:
                    continue
                
                # Build address
                street = tags_data.get('addr:street', '')
                city = tags_data.get('addr:city', location)
                state = tags_data.get('addr:state', '')
                
                address_parts = [p for p in [street, city, state] if p]
                address = ', '.join(address_parts) if address_parts else location
                
                businesses.append({
                    "name": name,
                    "phone": phone,
                    "address": address[:50],
                    "source": "osm"
                })
            
            print(f"✅ Found {len(businesses)} businesses")
            return businesses[:3] if businesses else mock_results(query, location)
            
    except Exception as e:
        print(f"OSM error: {e}")
        return mock_results(query, location)

def format_nigerian_phone(phone):
    """Convert various formats to standard +234XXXXXXXXXX"""
    if not phone:
        return None
    
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)
    
    # Format: +234XXXXXXXXXX (13 digits total)
    if digits.startswith('234') and len(digits) == 13:
        return '+' + digits
    elif digits.startswith('0') and len(digits) == 11:
        return '+234' + digits[1:]
    elif len(digits) == 10 and digits[0] in '789':
        # Sometimes people omit the leading 0
        return '+234' + digits
    else:
        return None

# ============================================
# FALLBACK MOCK DATA
# ============================================
def mock_results(query, location):
    """Fallback when OSM returns nothing"""
    print("⚠️ Using mock data (OSM returned no results)")
    
    if "plumber" in query.lower():
        return [
            {"name": "Quick Fix Plumbing", "phone": "+2348123456789", "address": location, "source": "mock"},
            {"name": "Pipe Masters", "phone": "+2348098765432", "address": location, "source": "mock"},
        ]
    elif "electrician" in query.lower():
        return [
            {"name": "PowerPro Electric", "phone": "+2347012345678", "address": location, "source": "mock"},
            {"name": "Spark Solutions", "phone": "+2347087654321", "address": location, "source": "mock"}
        ]
    else:
        return [
            {"name": f"{query.title()} Services", "phone": "+2348012345678", "address": location, "source": "mock"}
        ]

# ============================================
# QUERY PARSER
# ============================================
def parse_query(text):
    """Extract service type and location from user message"""
    text = text.lower().strip()
    
    # Categories we support
    categories = {
        'plumber': ['plumber', 'plumbing', 'pipe', 'leak', 'toilet', 'water'],
        'electrician': ['electrician', 'electrical', 'wiring', 'light', 'power'],
        'ac': ['ac', 'air condition', 'aircondition', 'cooling', 'hvac'],
        'generator': ['generator', 'gen', 'power supply', 'diesel'],
        'tailor': ['tailor', 'sewing', 'clothes', 'alteration'],
        'mechanic': ['mechanic', 'car repair', 'auto', 'workshop'],
        'carpenter': ['carpenter', 'woodwork', 'furniture'],
        'painter': ['painter', 'painting', 'wall'],
        'cleaner': ['cleaner', 'cleaning', 'wash'],
        'driver': ['driver', 'taxi', 'cab', 'chauffeur']
    }
    
    # Nigerian locations
    locations = ['lekki', 'yaba', 'ikeja', 'vi', 'ikoyi', 'surulere', 'ajah', 
                 'gbagada', 'ogudu', 'magodo', 'island', 'mainland', 'lagos',
                 'abuja', 'kano', 'ibadan', 'portharcourt', 'ph']
    
    # Find category
    category = None
    for cat, keywords in categories.items():
        if any(kw in text for kw in keywords):
            category = cat
            break
    
    # Find location
    found_location = None
    for loc in locations:
        if loc in text:
            found_location = loc.title()
            break
    
    # Default to Lagos if no location found
    if not found_location:
        found_location = 'Lagos'
    
    return {'category': category, 'location': found_location}

# ============================================
# WELCOME MESSAGE
# ============================================
WELCOME = """👋 Hello {first_name}!

I'm *BizVerify* — I find service providers that actually answer their phones.

🔍 *How to search:*
Just type what you need:
• "Plumber in Lekki"
• "Electrician Yaba"  
• "AC repair Ikoyi"
• "Generator mechanic"

I'll search our database and show you businesses with working phone numbers.

📍 *Currently covering:* Lagos, Abuja, Kano, Ibadan, Port Harcourt

💡 *Tip:* If you don't get results, try broader terms like "repair" or "services"
"""

# ============================================
# MAIN BOT LOOP
# ============================================
def run_bot():
    print("🚀 Starting BizVerify bot...")
    
    if not TELEGRAM_TOKEN:
        print("❌ ERROR: No TELEGRAM_BOT_TOKEN set!")
        return
    
    # Initialize analytics
    init_analytics_db()
    print("📊 Analytics database ready")
    
    bot = SimpleBot(TELEGRAM_TOKEN)
    print("✅ Bot connected! Waiting for messages...")
    
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
                user_id = user.get('id', chat_id)
                first_name = user.get('first_name', 'there')
                username = user.get('username', '')
                
                print(f"\n📩 Message from {first_name}: {text}")
                
                # Start command
                if text == '/start':
                    bot.send_message(chat_id, WELCOME.format(first_name=first_name))
                    continue
                
                # Analytics command (admin only - you can check stats)
                if text == '/stats' and str(user_id) == os.getenv("ADMIN_USER_ID", ""):
                    stats = get_analytics_summary()
                    stats_text = f"""📈 *Bot Statistics*
                    
Total Searches: {stats.get('total_searches', 0)}
Unique Users: {stats.get('unique_users', 0)}
Returning Users: {stats.get('returning_users', 0)}
Retention Rate: {stats.get('retention_rate', '0%')}

Top Searches:
"""
                    for query, count in stats.get('top_searches', []):
                        stats_text += f"• {query}: {count} times\n"
                    
                    bot.send_message(chat_id, stats_text)
                    continue
                
                # Parse the search query
                parsed = parse_query(text)
                
                if not parsed['category']:
                    bot.send_message(chat_id, 
                        "❓ I didn't understand. Try:\n"
                        "• *Plumber Lekki*\n"
                        "• *Electrician Yaba*\n"
                        "• *AC repair Ikoyi*\n\n"
                        "Or type /start for help")
                    continue
                
                # Send "searching" message
                searching_msg = f"🔍 Searching for *{parsed['category']}* in *{parsed['location']}*..."
                bot.send_message(chat_id, searching_msg)
                
                # Search OSM (FREE)
                businesses = search_places_osm(parsed['category'], parsed['location'])
                
                # Track this search in analytics
                track_search(user_id, username, parsed['category'], parsed['location'], len(businesses))
                
                # Format results
                if not businesses:
                    response = "😕 No results found. Try:\n• A different location\n• Broader terms like 'repair' or 'services'"
                    bot.send_message(chat_id, response)
                    continue
                
                # Build response
                lines = [f"🔍 *{parsed['category'].title()} in {parsed['location']}*\n"]
                
                for i, biz in enumerate(businesses, 1):
                    source_icon = "🗺️" if biz.get('source') == 'osm' else "📋"
                    lines.append(f"{i}. {source_icon} *{biz['name']}*")
                    lines.append(f"   📞 `{biz['phone']}`")
                    lines.append(f"   📍 _{biz['address']}_\n")
                
                lines.append("💡 *Tap the number to call*")
                
                if any(b.get('source') == 'mock' for b in businesses):
                    lines.append("\n_⚠️ Showing sample data. Real data coming soon!_")
                
                response = '\n'.join(lines)
                bot.send_message(chat_id, response)
                
                # Ask for feedback (simple yes/no)
                time.sleep(2)  # Wait for them to read
                bot.send_message(chat_id, 
                    "Was this helpful? Reply:\n"
                    "👍 *Yes* — Got what I needed\n"
                    "👎 *No* — Didn't find what I wanted")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

# ============================================
# START EVERYTHING
# ============================================
if __name__ == "__main__":
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask server for Render (keeps service alive)
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Starting web server on port {port}...")
    app.run(host='0.0.0.0', port=port)
