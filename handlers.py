from telegram import Update
from telegram.ext import ContextTypes
import asyncio
from config import config

# Simple in-memory storage for testing
users = {}

WELCOME = """
👋 Hello {first_name}!

I'm *BizVerify* — I find service providers that actually answer.

🔍 *How it works:*
1. Tell me what you need: "Plumber in Lekki"
2. I check the numbers *right now*
3. I send you only the ones that work

*Try it:* Type "Electrician Yaba"
"""

SEARCHING = "🔍 Searching for {category} in {location}...\n⏱ This takes ~30 seconds..."

def parse_query(text: str) -> dict:
    text_lower = text.lower()
    
    categories = {
        'plumber': ['plumber', 'plumbing', 'pipe', 'leak'],
        'electrician': ['electrician', 'electrical', 'wire', 'light'],
        'ac': ['ac', 'air condition', 'cooling', 'aircon'],
        'generator': ['generator', 'gen'],
    }
    
    locations = ['lekki', 'yaba', 'ikeja', 'victoria island', 'vi', 'ikoyi', 'surulere', 'maryland']
    
    category = None
    for cat, keywords in categories.items():
        if any(k in text_lower for k in keywords):
            category = cat
            break
    
    location = 'Lagos'
    for loc in locations:
        if loc in text_lower:
            location = loc.title()
            break
    
    return {'category': category, 'location': location}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"START: User {update.effective_user.id}")
    user = update.effective_user
    users[user.id] = {
        'name': user.first_name,
        'username': user.username
    }
    
    await update.message.reply_text(
        WELCOME.format(first_name=user.first_name or "there"),
        parse_mode='Markdown'
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text
    user = update.effective_user
    
    print(f"SEARCH: '{query_text}' from {user.id}")
    
    parsed = parse_query(query_text)
    print(f"PARSED: {parsed}")
    
    if not parsed['category']:
        await update.message.reply_text(
            "❓ I didn't understand. Try:\n"
            "• 'Plumber in Lekki'\n"
            "• 'Electrician Yaba'\n"
            "• 'AC repair Victoria Island'"
        )
        return
    
    # Send searching message
    msg = await update.message.reply_text(
        SEARCHING.format(
            category=parsed['category'].title(),
            location=parsed['location']
        )
    )
    
    try:
        # Import here to avoid startup issues
        from services.search import search_service
        from services.verification import verification_engine
        
        print("Calling search_service...")
        businesses = await search_service.search(parsed['category'], parsed['location'])
        print(f"Found {len(businesses)} businesses")
        
        if not businesses:
            await msg.edit_text("😕 No results found. Try a different location.")
            return
        
        # Verify (limit to 2 for cost)
        print("Verifying businesses...")
        verified = await verification_engine.verify_businesses(businesses[:2])
        print(f"Verified {len(verified)}")
        
        # Format results
        lines = [f"🔍 *{parsed['category'].title()} in {parsed['location']}*\n"]
        
        for i, biz in enumerate(verified, 1):
            v = biz.get('verification', {})
            status = v.get('status', 'UNKNOWN')
            
            if status == 'SUCCESS':
                icon, subtext = '✅', 'Verified just now'
            elif status == 'NO_ANSWER':
                icon, subtext = '⏰', 'No answer'
            else:
                icon, subtext = '❌', 'Not working'
            
            lines.append(f"{i}. {icon} *{biz['name']}*")
            lines.append(f"   📞 `{biz['phone']}`")
            lines.append(f"   _{subtext}_\n")
        
        response = '\n'.join(lines)
        print(f"Sending response: {response[:100]}...")
        await msg.edit_text(response, parse_mode='Markdown')
        print("Response sent!")
        
    except Exception as e:
        print(f"ERROR in search: {e}")
        import traceback
        traceback.print_exc()
        await msg.edit_text(f"😕 Error: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"GLOBAL ERROR: {context.error}")
    import traceback
    traceback.print_exc()
    if update and update.effective_message:
        await update.effective_message.reply_text("😕 Something went wrong. Please try again.")