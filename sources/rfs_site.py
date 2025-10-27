import asyncio, logging
from typing import Callable, Set
import httpx
from bs4 import BeautifulSoup

KEYS = ["Дюков", "брифинг", "итоги", "доклад", "пресс-конференция", "пресс конференция"]
BASE = "https://rfs.ru"
SLEEP = 60

class RfsSiteWatcher:
    def __init__(self, on_text: Callable[[str], None]):
        self.on_text = on_text
        self._seen: Set[str] = set()

    async def run(self):
        while True:
            try:
                await self._tick()
            except Exception as e:
                logging.exception("rfs.ru watcher error: %s", e)
            await asyncio.sleep(SLEEP)

    async def _tick(self):
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BASE}/news")
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("a.news-card__link"):
            href = a.get("href") or ""
            url = href if href.startswith("http") else BASE + href
            title = a.get_text(" ", strip=True)
            if url in self._seen:
                continue
            if any(k.lower() in title.lower() for k in KEYS):
                self._seen.add(url)
                text = await self._fetch_article(url)
                if text:
                    self.on_text(text[:4000])

    async def _fetch_article(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code != 200: return ""
        soup = BeautifulSoup(r.text, "lxml")
        parts = [p.get_text(" ", strip=True) for p in soup.select("article p")]
        return "\n".join(parts)
