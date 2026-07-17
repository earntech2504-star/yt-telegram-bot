import asyncio
import feedparser
import os
import re
import requests
import threading
import html
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
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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
    # 1. Sabse pehle yt-dlp se try (YT + FB share + Insta ke liye best hai)
    try:
        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'New Post')
            # Title ko clean karo
            title = html.escape(title)[:200]
            if "facebook" in url: title = f"🔵 {title}"
            elif "instagram" in url: title = f"🟣 {title}"
            return {'title': title, 'thumbnail': info.get('thumbnail', None)}
    except Exception as e:
        print(f"yt-dlp fail: {e}")

    # 2. Agar yt-dlp fail to website se og:image nikalo
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'}
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        html_text = r.text

        title = "🔗 New Link"
        if "facebook.com" in url or "fb.watch" in url: title = "🔵 Facebook Post"
        elif "instagram.com" in url: title = "🟣 Instagram Post"
        else:
            t_match = re.search(r'<title>(.*?)</title>', html_text, re.IGNORECASE | re.DOTALL)
            if t_match: title = html.escape(t_match.group(1).strip()[:200])

        thumb = None
        m1 = re.search(r'property=[\"\']og:image[\"\'][^>]*content=[\"\']([^\"\']+)[\"\']', html_text, re.IGNORECASE)
        m2 = re.search(r'content=[\"\']([^\"\']+)[\"\'][^>]*property=[\"\']og:image[\"\']', html_text, re.IGNORECASE)
        if m1: thumb = m1.group(1).replace("&amp;", "&")
        elif m2: thumb = m2.group(1).replace("&amp;", "&")

        return {'title': title, 'thumbnail': thumb}
    except Exception as e:
        print(f"OG fail: {e}")
        return {'title': '🔵 Facebook Post' if 'facebook' in url else '🔗 New Link', 'thumbnail': None}

async def handle_any_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    urls = re.findall(r'http[s]?://\S+', text)
    if not urls: return
    url = urls[0].strip()
    await update.message.reply_text(f"Link mil gaya, post kar raha hu: {url}")
    info = get_info_from_any_link(url)
    caption = f"<b>{info['title']}</b>\n\n{url}"
    try:
        if info['thumbnail']:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=info['thumbnail'], caption=caption, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='HTML')
        await update.message.reply_text("Done ✅")
    except Exception as e:
        print(f"Send photo fail, sending text: {e}")
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='HTML')
            await update.message.reply_text("Done ✅ (thumbnail block tha, link post ho gaya)")
        except Exception as e2:
            await update.message.reply_text(f"Error: {e2}")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ready hu! YT / FB / Insta / Website koi bhi bhej!")

async def rss_checker(app):
    print("RSS Started")
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
                            caption = f"<b>{html.escape(entry.title)}</b>\n\n{entry.link}"
                            await app.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='HTML')
                            save_posted_id(video_id)
                            posted_ids.add(video_id)
                except Exception as inner_e:
                    print(inner_e)
            await asyncio.sleep(600)
        except Exception as e:
            await asyncio.sleep(60)

async def post_init(application):
    asyncio.create_task(rss_checker(application))

web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot Running"
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
