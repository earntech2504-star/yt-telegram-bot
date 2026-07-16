import asyncio, feedparser, os, re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import yt_dlp

load_dotenv()

# --- FINAL IDs ---
CHANNEL_ID = -1004347425414
BOT_TOKEN = os.getenv("BOT_TOKEN")

RSS_FEEDS = [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UC1NtcHxG3wiyhtbbPmIaMnA", # MX Player
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCbg1fucJLGhyRG9bEb9zqLA", # Atrangii
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCBWz-Q6Lg6QjtUqnKZI01DQ", # Kuku TV
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCw82_BrKru_CjqIuTzf04Kw" # ALTT
]

# Teri Amazon wali aur dusri API ka code yahan rahega, usko mat chedna

def get_info_from_any_link(url):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'New Video'),
                'thumbnail': info.get('thumbnail', None)
            }
    except:
        return {'title': 'New Update', 'thumbnail': None}

async def handle_any_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    urls = re.findall(r'http[s]?://\S+', text)
    if not urls:
        return

    url = urls[0]
    await update.message.reply_text(f"Link mil gaya bhai, post kar raha hu: {url}")

    info = get_info_from_any_link(url)
    caption = f"**{info['title']}**\n\n{url}"

    try:
        if info['thumbnail']:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=info['thumbnail'], caption=caption, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='Markdown')
        await update.message.reply_text("Done ✅ Channel pe post ho gaya.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bhai main ready hu. Koi bhi link bhej, main channel pe daal dunga. RSS auto chalta rahega.")

async def rss_checker(app):
    while True:
        try:
            for feed_url in RSS_FEEDS:
                feed = feedparser.parse(feed_url)
                if feed.entries:
                    video = feed.entries[0]
                    text = f"{video.title}\n{video.link}"
                    # Yahan pe tu check laga sakta hai ki duplicate na post ho
                    # await app.bot.send_message(chat_id=CHANNEL_ID, text=text)
            await asyncio.sleep(3600) # Har 1 ghante me check
        except Exception as e:
            print(f"RSS Error: {e}")
            await asyncio.sleep(60)

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_link))

    # RSS ko background me chalao
    asyncio.create_task(rss_checker(app))

    print("Bot started... Koi bhi link bhej ke check kar.")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())