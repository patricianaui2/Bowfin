import os
from re import sub
import time
from urllib import response
import requests
from threading import Thread
from flask import Flask

app = Flask(__name__)

# --- CONFIGURATION & INITIALIZATION ---

# Load Telegram Configuration Globally
TELEGRAM_CONFIG = {
    "TOKEN": os.environ.get("TOKEN", "").strip(),
    "ID": os.environ.get("ID", "").strip()
}

# Dynamic Environment Routing
SUBREDDITS_STR = os.environ.get("SUBREDDITS", "aww,animalsdoingstuff,Eyebleach")
KEYWORDS_STR = os.environ.get("KEYWORDS", "cute,wholesome,happy")

SUBREDDITS = [s.strip() for s in SUBREDDITS_STR.split(",") if s.strip()]
KEYWORDS = [k.strip().lower() for k in KEYWORDS_STR.split(",") if k.strip()]

# Initialize Nvidia AI Client
ai_client = None
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "").strip()

if NVIDIA_KEY:
    try:
        from openai import OpenAI
        ai_client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=NVIDIA_KEY
        )
        print("🧠 Nvidia Llama Nemotron Super initialized successfully! Lead scoring active.", flush=True)
    except ImportError:
        print("ℹ️ 'openai' library uninstalled. Falling back to classic keyword alerts.", flush=True)
else:
    print("ℹ️ NVIDIA_API_KEY missing. Falling back to classic keyword alerts.", flush=True)

print(f"📡 Monitoring Subreddits: {SUBREDDITS}", flush=True)
print(f"🔑 Tracking Keywords: {KEYWORDS}", flush=True)

processed_posts = set()

# --- FLASK HEARTBEAT ---

@app.route('/')
def home():
    return "Bowfin is online!"

# --- CORE LOGIC FUNCTIONS ---

def classify_lead_intent(title, body):
    """
    Uses Nvidia Llama Nemotron Super 49B v1.5 to assess structural intent of a post.
    Parses and returns a structured string formatted exactly as:
    [TIER_BADGE] [TIER_NAME] INTENT: [Analysis Reason]
    """
    if not ai_client:
        return "⚠️ AI OFFLINE: Classic Keyword Match"
        
    system_instruction = """You are an expert lead generation analyzer assessing Reddit posts for small businesses and founders.
Analyze the user's post and categorize it into exactly one of these tiers based on intent:

- 🔴 HIGH INTENT: The user is explicitly asking for a tool, product, software recommendation, hiring service, or looking to buy right now.
- 🟡 MEDIUM INTENT: The user is asking a relevant industry question, researching options, or talking about an abstract workflow problem but hasn't explicitly asked to buy yet.
- ⚪ LOW INTENT: The user is just complaining, venting, sharing a meme, or discussing something unrelated to a professional need.

Output Format (Strictly follow this exact layout, nothing else):
[TIER] | Reason: [One brief sentence explaining why]"""

    try:
        response = ai_client.chat.completions.create(
            model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Post Title: {title}\nPost Body: {body}"}
            ],
            temperature=0.2,  
            max_tokens=1024         
        )
        
        content = getattr(response.choices[0].message, 'content', None)
        reasoning = getattr(response.choices[0].message, 'reasoning', None) or getattr(response.choices[0].message, 'reasoning_content', None)
        
        raw_text = (content or reasoning or "").strip()
            
        if raw_text:
            # Parse layout structure if model adds its default chain of thought prefix strings
            if "Reason:" in raw_text:
                parts = raw_text.split("|", 1)
                tier_part = parts[0].replace("[", "").replace("]", "").strip()
                # Ensure the tier name matches standard uppercase labels
                if "HIGH" in tier_part:
                    tier_label = "🔴 HIGH INTENT"
                elif "MEDIUM" in tier_part:
                    tier_label = "🟡 MEDIUM INTENT"
                else:
                    tier_label = "⚪️ LOW INTENT"
                
                reason_part = parts[1].replace("Reason:", "").strip()
                return f"{tier_label}: {reason_part}"
            
            # Simple safe slice truncation if layout falls out of bounds
            return raw_text if len(raw_text) < 200 else raw_text[:200] + "..."
            
    except Exception as e:
        print(f"⚠️ NVIDIA processing error: {e}", flush=True)
    return "⚪️ UNKNOWN INTENT: Processing error occurred."

def send_telegram_message(message):
    token = TELEGRAM_CONFIG["TOKEN"]
    chat_id = TELEGRAM_CONFIG["ID"]
    
    if not token or not chat_id:
        print("❌ Telegram Error: Configuration missing!", flush=True)
        return False

    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_notification": False
    }
    
    try:
        response = requests.post(telegram_url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Alert sent to Telegram successfully!", flush=True)
            return True
        print(f"❌ Telegram API Error {response.status_code}: {response.text}", flush=True)
    except Exception as e:
        print(f"⚠️ Connection error sending to Telegram: {e}", flush=True)
    return False

def check_reddit():
    """
    Fetches the 10 newest posts per subreddit via PullPush API.
    Does NOT require a Reddit App, Client Secret, or OAuth key.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BowfinLeadBot/2.0"
    }

    for sub in SUBREDDITS:
        try:
            # PullPush public endpoint
            url = f"https://api.pullpush.io/topic?subreddit={sub}&size=10"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                posts = data.get("data", [])

                for post in posts:
                    post_id = post.get("id", "")
                    title = post.get("title", "No Title")
                    body = post.get("selftext", "")
                    # Construct permalink or use full_link
                    permalink = post.get("permalink", f"/r/{sub}/comments/{post_id}")

                    if post_id in processed_posts:
                        continue

                    combined_text = (title + " " + body).lower()
                    for keyword in KEYWORDS:
                        if keyword in combined_text:
                            ai_analysis = classify_lead_intent(title, body)
                            alert_text = (
                                f"📌 New Potential Lead in r/{sub}!\n\n"
                                f"Title: {title}\n\n"
                                f"{ai_analysis}\n\n"
                                f"Link: https://reddit.com{permalink}"
                            )
                            send_telegram_message(alert_text)
                            time.sleep(1)
                            break

                    processed_posts.add(post_id)

                print(f"✅ Successfully checked r/{sub} via PullPush ({len(posts)} posts received)", flush=True)

            else:
                print(f"⚠️ PullPush API HTTP Error on r/{sub}: {response.status_code}", flush=True)

        except Exception as e:
            print(f"❌ Exception checking r/{sub}: {e}", flush=True)

# --- BACKGROUND THREAD RADAR ---

def radar_loop():
    print("🚀 Starting High-Volume Bowfin loop...", flush=True)
    while True:
        check_reddit()
        time.sleep(300) 

def start_background_workers():
    t = Thread(target=radar_loop)
    t.daemon = True 
    t.start()

start_background_workers()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
