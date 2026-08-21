import os
import time
from threading import Thread
from flask import Flask
from curl_cffi import requests
import feedparser

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
        response = requests.post(url, json=payload, timeout=10, impersonate="chrome")
        return response.status_code == 200
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}", flush=True)
    return False

def check_reddit():
    """
    Fetches newest posts via Reddit RSS feeds to bypass JSON datacenter bans.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    for sub in SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{sub}/new.rss"
            response = requests.get(url, headers=headers, impersonate="chrome", timeout=10)

            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                entries = feed.entries

                for entry in entries:
                    post_id = getattr(entry, "id", getattr(entry, "link", ""))
                    title = getattr(entry, "title", "")
                    body = getattr(entry, "summary", "")
                    link = getattr(entry, "link", "")

                    if post_id in processed_posts:
                        continue

                    combined_text = f"{title} {body}".lower()
                    for keyword in KEYWORDS:
                        if keyword in combined_text:
                            alert_text = (
                                f"📌 New Lead in r/{sub}!\n\n"
                                f"Title: {title}\n\n"
                                f"Link: {link}"
                            )
                            send_telegram_message(alert_text)
                            time.sleep(1)
                            break

                    processed_posts.add(post_id)

                print(f"✅ Checked r/{sub} via RSS ({len(entries)} posts)", flush=True)
            else:
                print(f"⚠️ Reddit RSS Error {response.status_code} on r/{sub}", flush=True)

        except Exception as e:
            print(f"❌ Exception checking r/{sub}: {e}", flush=True)

# --- BACKGROUND THREAD RADAR ---

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
