import os, asyncio, logging, requests
from typing import Callable, Optional

API_KEY = os.getenv("YOUTUBE_API_KEY")
CHANNEL_ID = os.getenv("RFS_CHANNEL_ID", "UCLNgRqvauqKU6SOzdAJSQaw")
POLL_SEC = int(os.getenv("POLL_YOUTUBE_SECONDS", "15"))

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

class YouTubeLiveWatcher:
    # Ищет активный LIVE на канале РФС и получает текст:
    # 1) Live‑субтитры (если есть)
    # 2) Fallback: yt-dlp + faster-whisper (локальная расшифровка)
    def __init__(self, on_text: Callable[[str], None]):
        self.on_text = on_text
        self._seen_caption_ids = set()

    async def run(self):
        while True:
            try:
                live_id = self._find_live_video_id()
                if live_id:
                    await self._consume_live(live_id)
                else:
                    await asyncio.sleep(POLL_SEC)
            except Exception as e:
                logging.exception("YouTube watcher error: %s", e)
                await asyncio.sleep(POLL_SEC)

    def _find_live_video_id(self) -> Optional[str]:
        if API_KEY:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "channelId": CHANNEL_ID,
                "eventType": "live",
                "type": "video",
                "order": "date",
                "maxResults": 1,
                "key": API_KEY,
            }
            r = requests.get(url, params=params, timeout=10)
            if r.ok and r.json().get("items"):
                return r.json()["items"][0]["id"]["videoId"]
        try:
            html = requests.get("https://www.youtube.com/c/%D0%A0%D0%A4%D0%A1%D0%A2%D0%92/streams", timeout=10).text
            for marker in ('"isLive":true', '"badgeLabel":{"simpleText":"LIVE"'):
                if marker in html:
                    pos = html.find("watch?v=")
                    if pos != -1:
                        return html[pos+8:pos+19]
        except Exception:
            pass
        return None

    async def _consume_live(self, video_id: str):
        logging.info("LIVE detected: %s", video_id)
        if YouTubeTranscriptApi:
            try:
                transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                # предпочитаем русские или auto‑generated
                candidate = None
                for tr in transcripts:
                    if tr.language_code.startswith("ru"):
                        candidate = tr
                        break
                    if tr.is_generated:
                        candidate = tr
                if candidate is not None:
                    items = candidate.fetch()
                    new = 0
                    for item in items:
                        cid = f"{item['start']:.2f}-{item['duration']:.2f}"
                        if cid in self._seen_caption_ids:
                            continue
                        self._seen_caption_ids.add(cid)
                        self.on_text(item.get("text",""))
                        new += 1
                    if new == 0:
                        await asyncio.sleep(5)
                    return
            except Exception as e:
                logging.info("Captions unavailable, switching to fallback STT: %s", e)

        await self._fallback_stt(video_id)

    async def _fallback_stt(self, video_id: str):
        # yt-dlp аудио + faster‑whisper
        try:
            proc = await asyncio.create_subprocess_shell(
                f'yt-dlp -f bestaudio -o - https://www.youtube.com/watch?v={video_id}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
        except Exception as e:
            logging.error("yt-dlp start failed: %s", e); return

        from transcribe.stream_stt import stream_transcribe_stdin
        async for text in stream_transcribe_stdin(proc.stdout):
            if text:
                self.on_text(text)
