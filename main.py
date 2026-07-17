import asyncio
import feedparser
import os
import re
import requests
import threading
from flask import Flask
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import yt_dlp

load_dotenv()
CHANNEL_ID = -1004347425414
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN nahi mila!")
    exit(1)

RSS_FEEDS = [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UC1NtcHxG3wiyhtbbPmIaMnA",
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCbg1fucJLGhyRG9bEb9zqLA",
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCBWz-Q6Lg6QjtUqnKZI01DQ",
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCw82_BrKru_CjqIuTzf04Kw"
]

POSTED_FILE = "posted_videos.txt"

def get_cookie_file():
    if os.path.exists("/etc/secrets/cookies.txt"):
        return "/etc/secrets/cookies.txt"
    if os.path.exists("cookies.txt"):
        return "cookies.txt"
    return None

def get_ydl_opts():
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'nocheckcertificate': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    cookie_file = get_cookie_file()
    if cookie_file:
        opts['cookiefile'] = cookie_file
    return opts

def get_posted_ids():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_posted_id(video_id):
    with open(POSTED_FILE, "a", encoding="utf-8") as f:
        f.write(video_id + "\n")

def get_info_from_any_link(url):
    title = "New Link"
    thumb = None

    # Common headers for FB/Insta/Web
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }

    # 1. YouTube ke liye pehle yt-dlp try karo (best thumbnail)
    if "youtube.com" in url or "youtu.be" in url:
        try:
            with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
                info = ydl.extract_info(url, download=False)
                return {'title': info.get('title', 'YouTube Video'), 'thumbnail': info.get('thumbnail', None)}
        except Exception as e:
            print(f"yt-dlp yt error: {e}")

    # 2. FB / Insta / Website ke liye og:image nikalo
    try:
        r = requests.get(url, headers=headers, timeout=15)
        html = r.text

        # Title logic
        t_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if t_match:
            raw_title = t_match.group(1).strip()
            if "facebook" in url: title = f"🔵 {raw_title[:150]}"
            elif "instagram" in url: title = f"🟣 {raw_title[:150]}"
            else: title = raw_title[:200]
        else:
            if "facebook" in url: title = "🔵 Facebook Post"
            elif "instagram" in url: title = "🟣 Instagram Reel"

        # og:image logic
        m1 = re.search(r'<meta[^>]*property=[\"\']og:image[\"\'][^>]*content=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE)
        m2 = re.search(r'<meta[^>]*content=[\"\']([^\"\']+)[\"\'][^>]*property=[\"\']og:image[\"\']', html, re.IGNORECASE)
        if m1: thumb = m1.group(1)
        elif m2: thumb = m2.group(1)

        # FB ka image link me &amp; hota hai usko fix karo
        if thumb:
            thumb = thumb.replace("&amp;", "&")

        return {'title': title, 'thumbnail': thumb}

    except Exception as e:
        print(f"Website parse error: {e}")
        if "facebook" in url: return {'title': '🔵 Facebook Post', 'thumbnail': None}
        if "instagram" in url: return {'title': '🟣 Instagram Post', 'thumbnail': None}
        return {'title': '🔗 New Link', 'thumbnail': None}

async def handle_any_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    urls = re.findall(r'http[s]?://\S+', text)
    if not urls: return
    url = urls[0].split()[0]
    await update.message.reply_text(f"Link mil gaya bhai, post kar raha hu: {url}")
    info = get_info_from_any_link(url)

    caption = f"<b>{info['title']}</b>\n\n{url}"

    try:
        if info['thumbnail']:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=info['thumbnail'], caption=caption, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='HTML')
        await update.message.reply_text("Done ✅ Channel pe thumbnail ke saath post ho gaya.")
    except Exception as e:
        print(f"Send error: {e}")
        # Agar photo fail ho to text se bhej de
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='HTML')
            await update.message.reply_text("Done ✅ (photo fail, text post ho gaya)")
        except Exception as e2:
            await update.message.reply_text(f"Error: {e2}")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bhai ready hu! YT / Insta / FB / Website - koi bhi link bhej, thumbnail ke saath channel pe daal dunga!")

async def rss_checker(app):
    print("RSS Checker Started...")
    HEADERS = {'User-Agent': 'Mozilla/5.0'}
    while True:
        try:
            posted_ids = get_posted_ids()
            for feed_url in RSS_FEEDS:
                try:
                    resp = requests.get(feed_url, headers=HEADERS, timeout=20)
                    if resp.status_code!= 200: continue
                    feed = feedparser.parse(resp.content)
                    for entry in feed.entries[:2]:
                        video_id = getattr(entry, 'yt_videoid', None) or entry.id
                        if video_id not in posted_ids:
                            caption = f"<b>{entry.title}</b>\n\n{entry.link}"
                            await app.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='HTML')
                            save_posted_id(video_id)
                            posted_ids.add(video_id)
                            await asyncio.sleep(5)
                except Exception as inner_e:
                    print(f"Feed Error: {inner_e}")
            await asyncio.sleep(600)
        except Exception as e:
            print(f"RSS Error: {e}")
            await asyncio.sleep(60)

async def post_init(application):
    asyncio.create_task(rss_checker(application))

web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Running"
def run_web(): web_app.run(host='0.0.0.0', port=10000)
threading.Thread(target=run_web, daemon=True).start()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_link))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
