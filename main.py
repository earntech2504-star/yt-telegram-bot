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

def get_posted_ids():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_posted_id(video_id):
    with open(POSTED_FILE, "a", encoding="utf-8") as f:
        f.write(video_id + "\n")

def get_info_from_any_link(url):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {'title': info.get('title', 'New Video'), 'thumbnail': info.get('thumbnail', None)}
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return {'title': 'New Update', 'thumbnail': None}

async def handle_any_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    urls = re.findall(r'http[s]?://\S+', text)
    if not urls: return
    url = urls[0]
    await update.message.reply_text(f"Link mil gaya bhai, post kar raha hu: {url}")
    info = get_info_from_any_link(url)
    caption = f"<b>{info['title']}</b>\n\n{url}"
    try:
        if info['thumbnail']:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=info['thumbnail'], caption=caption, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='HTML')
        await update.message.reply_text("Done ✅ Channel pe post ho gaya.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bhai main ready hu. RSS auto chalta rahega.")

async def rss_checker(app):
    print("RSS Checker Started...")
    HEADERS = {'User-Agent': 'Mozilla/5.0'}
    while True:
        try:
            posted_ids = get_posted_ids()
            for feed_url in RSS_FEEDS:
                try:
                    print(f"Checking: {feed_url}")
                    resp = requests.get(feed_url, headers=HEADERS, timeout=20)
                    if resp.status_code!= 200: continue
                    feed = feedparser.parse(resp.content)
                    for entry in feed.entries[:2]:
                        video_id = getattr(entry, 'yt_videoid', None) or entry.id
                        if video_id not in posted_ids:
                            print(f"New Video Found: {entry.title}")
                            caption = f"<b>{entry.title}</b>\n\n{entry.link}"
                            await app.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='HTML')
                            save_posted_id(video_id)
                            posted_ids.add(video_id)
                            await asyncio.sleep(5)
                except Exception as inner_e:
                    print(f"Error for feed {feed_url}: {inner_e}")
            print("Sleeping 10 min...")
            await asyncio.sleep(600)
        except Exception as e:
            print(f"RSS Main Error: {e}")
            await asyncio.sleep(60)

async def post_init(application):
    asyncio.create_task(rss_checker(application))

# --- FLASK FOR FREE WEB SERVICE ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Running"
def run_web(): web_app.run(host='0.0.0.0', port=10000)
threading.Thread(target=run_web, daemon=True).start()
# ----------------------------------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_link))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()