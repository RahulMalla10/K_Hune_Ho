from __future__ import annotations
import concurrent.futures
import logging
import random
import time
import urllib.parse
from typing import List, Dict, Any, Callable

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
try:
    from gnews import GNews
    GNEWS_AVAILABLE = True
except ImportError:
    GNEWS_AVAILABLE = False
try:
    from duckduckgo_search import DDGS
    from duckduckgo_search.exceptions import DuckDuckGoSearchException
    DDGS_AVAILABLE = True
    _DDGS_SAFE_IMPERSONATES = ("random",)
    try:
        import primp

        _parts = getattr(primp, "__version__", "0").split(".")[:2]
        _v = tuple(int(p) for p in _parts if p.isdigit())
        if len(_v) >= 2 and _v >= (1, 0):
            _DDGS_SAFE_IMPERSONATES = (
                "chrome_146",
                "chrome_147",
                "chrome_148",
                "chrome",
                "safari_26",
                "safari_26.3",
                "safari",
                "edge_146",
                "edge",
                "firefox_148",
                "firefox",
                "random",
            )
    except (ImportError, ValueError):
        pass
    DDGS._impersonates = _DDGS_SAFE_IMPERSONATES
except ImportError:
    DDGS_AVAILABLE = False
    DuckDuckGoSearchException = Exception

class NewsRetriever:
    def __init__(self, max_articles: int = 15, time_range: str = "week", verbose: bool = False):
        self.max_articles = max_articles
        self.time_range = time_range
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.last_search_status: list[str] = []

        for name in ("duckduckgo_search", "primp", "httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)

        self._days_map = {"day": 1, "week": 7, "month": 30}
        self._days = self._days_map.get(self.time_range, 7)
        self._ddg_timelimit = {"day": "d", "week": "w", "month": "m"}.get(self.time_range)

    def _log(self, msg: str) -> None:
        self.last_search_status.append(msg)
        if self.verbose:
            self.logger.info(msg)

    def _query_variants(self, query: str) -> list[str]:
        q = query.strip()
        variants = [q]
        short = " ".join(w for w in q.split() if w.lower() not in ("in", "the", "a", "an", "of"))
        if short != q and len(short) > 8:
            variants.append(short)
        words = q.split()
        if len(words) > 5:
            variants.append(" ".join(words[:5]))
        if "south asia" in q.lower():
            variants.append(q.lower().replace("south asia", "asia"))
        if "news" not in q.lower():
            variants.append(f"{words[0]} {words[1]} news" if len(words) >= 2 else f"{q} news")
        seen: set[str] = set()
        out: list[str] = []
        for v in variants:
            v = v.strip()
            if v and v not in seen:
                seen.add(v)
                out.append(v)
        return out[:4]

    def search(self, query: str) -> List[Dict[str, Any]]:
        self.last_search_status = []
        if self.verbose:
            self.logger.info("Searching for news: %s", query)

        sources: list[tuple[str, Callable[[str], list]]] = [
            ("DuckDuckGo News", self._search_duckduckgo),
            ("Google News RSS", self._search_google_rss),
            ("GNews", self._search_gnews),
        ]

        def _search_source(label: str, fn: Callable[[str], list]) -> tuple[str, list[dict]]:
            try:
                articles = fn(query)
                return label, articles
            except Exception as exc:
                self._log(f"{label} error: {exc}")
                return label, []

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(sources)))
        future_to_source = {
            executor.submit(_search_source, label, fn): label for label, fn in sources
        }

        for future in concurrent.futures.as_completed(future_to_source):
            label = future_to_source[future]
            _, articles = future.result()
            if articles:
                result = self._dedupe(articles)[: self.max_articles]
                self._log(f"{label}: {len(result)} articles")
                executor.shutdown(wait=False)
                return result
            self._log(f"{label}: 0 results")

        executor.shutdown(wait=True)
        return []

    def _dedupe(self, articles: list[dict]) -> list[dict]:
        seen: set[str] = set()
        unique: list[dict] = []
        for article in articles:
            key = article.get("url") or article.get("title", "")
            if not key:
                continue
            if key not in seen:
                seen.add(key)
                unique.append(article)
        return unique

    def _search_google_rss(self, query: str) -> List[Dict[str, Any]]:
        if not FEEDPARSER_AVAILABLE:
            return []
        encoded = urllib.parse.quote(query)
        url = (
            f"https://news.google.com/rss/search?"
            f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
        )
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[: self.max_articles]:
            articles.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "snippet": entry.get("summary", "") or entry.get("title", ""),
                "date": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", "") if hasattr(entry, "source") else "",
            })
        return [a for a in articles if a.get("title")]

    def _search_gnews(self, query: str) -> List[Dict[str, Any]]:
        if not GNEWS_AVAILABLE:
            return []
        articles: list[dict] = []
        for country in ("US", "IN", "GB"):
            try:
                google_news = GNews(
                    language="en",
                    country=country,
                    max_results=self.max_articles,
                    period=f"{self._days}d",
                )
                news = google_news.get_news(query)
                if not news:
                    continue
                for item in news:
                    publisher = item.get("publisher") or {}
                    articles.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", "") or item.get("title", ""),
                        "date": item.get("published date", ""),
                        "source": (
                            publisher.get("title", "")
                            if isinstance(publisher, dict)
                            else str(publisher)
                        ),
                    })
                if articles:
                    return articles
            except Exception as e:
                self._log(f"GNews ({country}): {e}")
        return articles

    def _search_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        if not DDGS_AVAILABLE:
            return []

        strategies = [
            lambda q: self._ddg_news(q, timelimit=None),
            lambda q: self._ddg_news(q, timelimit=self._ddg_timelimit),
            lambda q: self._ddg_text(q, timelimit=None),
        ]

        for attempt, fn in enumerate(strategies):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(1.5, 3.0))
                articles = fn(query)
                if articles:
                    return articles
            except DuckDuckGoSearchException as e:
                self._log(f"DuckDuckGo rate limit: {e}")
                time.sleep(2)
            except Exception as e:
                self._log(f"DuckDuckGo error: {e}")
        return []

    def _ddg_news(self, query: str, timelimit: str | None) -> List[Dict[str, Any]]:
        articles: list[dict] = []
        with DDGS() as ddgs:
            kwargs: dict = {
                "keywords": query,
                "region": "wt-wt",
                "safesearch": "moderate",
                "max_results": self.max_articles,
            }
            if timelimit:
                kwargs["timelimit"] = timelimit
            results = list(ddgs.news(**kwargs))
            for result in results:
                title = result.get("title", "")
                if not title:
                    continue
                articles.append({
                    "title": title,
                    "url": result.get("url", "") or result.get("href", "") or result.get("link", ""),
                    "snippet": result.get("body", "") or result.get("excerpt", "") or title,
                    "date": result.get("date", ""),
                    "source": result.get("source", ""),
                })
        return articles

    def _ddg_text(self, query: str, timelimit: str | None) -> List[Dict[str, Any]]:
        articles: list[dict] = []
        with DDGS() as ddgs:
            kwargs: dict = {
                "keywords": f"{query} news",
                "region": "wt-wt",
                "max_results": self.max_articles,
            }
            if timelimit:
                kwargs["timelimit"] = timelimit
            results = list(ddgs.text(**kwargs))
            for result in results:
                title = result.get("title", "")
                if not title:
                    continue
                articles.append({
                    "title": title,
                    "url": result.get("href", "") or result.get("url", ""),
                    "snippet": result.get("body", "") or title,
                    "date": result.get("date", ""),
                    "source": result.get("source", ""),
                })
        return articles
