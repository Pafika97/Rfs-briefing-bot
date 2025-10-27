import asyncio, os, logging
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
from sources.youtube_live import YouTubeLiveWatcher
from sources.rfs_site import RfsSiteWatcher
from summarize.summarizer import RollingSummarizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
if not (BOT_TOKEN and CHAT_ID):
    raise SystemExit("Need TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")

bot = Bot(token=BOT_TOKEN)

WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", "180"))
SUMMARY_PUSH_SECONDS = int(os.getenv("SUMMARY_PUSH_SECONDS", "45"))

summarizer = RollingSummarizer(window_seconds=WINDOW_SECONDS)
yt_watcher = YouTubeLiveWatcher(on_text=summarizer.feed_text)
rfs_watcher = RfsSiteWatcher(on_text=summarizer.feed_text)

_last_sent_fingerprints = set()

async def push_summaries_loop():
    while True:
        await asyncio.sleep(SUMMARY_PUSH_SECONDS)
        bullets, fp = summarizer.get_bullets()
        if not bullets or fp in _last_sent_fingerprints:
            continue
        _last_sent_fingerprints.add(fp)
        txt = "🟢 <b>Брифинг главы РФС — тезисы (онлайн)</b>\n" + "\n".join(f"• {b}" for b in bullets)
        try:
            await bot.send_message(chat_id=CHAT_ID, text=txt, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except Exception as e:
            logging.exception("Telegram send failed: %s", e)

async def main():
    tasks = [
        asyncio.create_task(yt_watcher.run()),
        asyncio.create_task(rfs_watcher.run()),
        asyncio.create_task(push_summaries_loop()),
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
