import asyncio, feedparser, os
from dotenv import load_dotenv
from telegram import Bot

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

async def main():
    bot = Bot(token=BOT_TOKEN)
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        if feed.entries:
            video = feed.entries[0]
            text = f"{video.title}\n{video.link}"
            await bot.send_message(chat_id=CHANNEL_ID, text=text)
            print(f"Sent: {video.title}")

if __name__ == "__main__":
    asyncio.run(main())