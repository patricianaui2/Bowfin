import os
import time
from threading import Thread
from flask import Flask
from curl_cffi import requests  # Replaces standard requests to bypass Cloudflare

app = Flask(__name__)

# --- CONFIGURATION ---

def get_clean_env(key, default=""):
    return os.environ.get(key, default).strip().replace('"', '').replace("'", "")

TELEGRAM_CONFIG = {
    "TOKEN": get_clean_env("TOKEN"),
    "ID": get_clean_env("ID")
}

SUBREDDITS_STR = get_clean_env("SUBREDDITS", "solofounders,startups,saas,marketing")
KEYWORDS_STR = get_clean_env("KEYWORDS", "tool,recommendation,looking for,help")

SUBREDDITS = [s.strip() for s in SUBREDDITS_STR.split(",") if s.strip()]
KEYWORDS = [k.strip().lower() for k in KEYWORDS_STR.split(",") if k.strip()]

# Initialize Nvidia AI Client
ai_client = None
NVIDIA_KEY = get_clean_env("NVIDIA_API_KEY")

if NVIDIA_KEY:
    try:
        from openai import OpenAI
        ai_client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=NVIDIA_KEY
        )
        print("🧠 Nvidia AI initialized successfully!", flush=True)
    except Exception as e:
        print(f"⚠️ AI init warning: {e}", flush=True)

processed_posts = set()

# --- FLASK HEARTBEAT ---

@app.route('/')
def home():
    return "Bowfin is online!"

# --- CORE LOGIC ---

def send_telegram_message(message):
    token = TELEGRAM_CONFIG["TOKEN"]
    chat_id = TELEGRAM_CONFIG["ID"]
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "disable_notification": False}
    
    try:
        # Using curl_cffi for Telegram as well
        response = requests.post(url, json=payload, timeout=10, impersonate="chrome")
        return response.status_code == 200
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}", flush=True)
    return False

def check_reddit():
    """
    Fetches newest posts via public Redlib mirrors to bypass Render datacenter IP blocks.
    """
    # List of reliable Redlib instances
    mirrors = [
        "https://safereddit.com",
        "https://redlib.catsarch.com"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BowfinLeadBot/3.0"
    }

    for sub in SUBREDDITS:
        fetched = False
        for base_url in mirrors:
            try:
                url = f"{base_url}/r/{sub}/new.json"
                response = requests.get(url, headers=headers, impersonate="chrome", timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    posts = data.get("data", {}).get("children", [])

                    for item in posts:
                        post = item.get("data", {})
                        post_id = post.get("id", "")
                        title = post.get("title", "")
                        body = post.get("selftext", "")
                        permalink = post.get("permalink", f"/r/{sub}/comments/{post_id}")

                        if post_id in processed_posts:
                            continue

                        combined_text = f"{title} {body}".lower()
                        for keyword in KEYWORDS:
                            if keyword in combined_text:
                                alert_text = (
                                    f"📌 New Lead in r/{sub}!\n\n"
                                    f"Title: {title}\n\n"
                                    f"Link: https://reddit.com{permalink}"
                                )
                                send_telegram_message(alert_text)
                                time.sleep(1)
                                break

                        processed_posts.add(post_id)

                    print(f"✅ Successfully checked r/{sub} via {base_url} ({len(posts)} posts)", flush=True)
                    fetched = True
                    break  # Exit mirror loop upon success

                else:
                    print(f"⚠️ {base_url} returned {response.status_code} for r/{sub}", flush=True)

            except Exception as e:
                print(f"⚠️ Mirror failure on {base_url} for r/{sub}: {e}", flush=True)

        if not fetched:
            print(f"❌ Failed to fetch r/{sub} across all mirrors.", flush=True)

def radar_loop():
    print("🚀 Bowfin loop starting...", flush=True)
    send_telegram_message("🟢 Bowfin Instance Online!")
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
