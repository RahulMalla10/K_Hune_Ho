import logging
import random
import time
from typing import List, Dict, Any

try:
    from gnews import GNews
    GNEWS_AVAILABLE = True
except ImportError:
    GNEWS_AVAILABLE = False
    logging.warning("gnews package not installed. Please install it with: pip install gnews")

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logging.warning("duckduckgo-search package not installed. Please install it with: pip install duckduckgo-search")


class NewsRetriever:
    def __init__(self, max_articles: int = 15, time_range: str = "week", verbose: bool = False):
        self.max_articles = max_articles
        self.time_range = time_range
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)

        self._days_map = {
            "day": 1,
            "week": 7,
            "month": 30
        }
        self._days = self._days_map.get(self.time_range, 7)

    def search(self, query: str) -> List[Dict[str, Any]]:
        if self.verbose:
            self.logger.info(f"Searching for news: {query}")

        if GNEWS_AVAILABLE:
            articles = self._search_gnews(query)
            if articles:
                if self.verbose:
                    self.logger.info(f"Retrieved {len(articles)} articles from GNews")
                seen_urls = set()
                unique_articles = []
                for article in articles:
                    if article['url'] not in seen_urls:
                        seen_urls.add(article['url'])
                        unique_articles.append(article)
                return unique_articles[:self.max_articles]

        if DDGS_AVAILABLE:
            if self.verbose:
                self.logger.info("Falling back to DuckDuckGo search")
            articles = self._search_duckduckgo(query)
            if articles:
                return articles[:self.max_articles]

        self.logger.warning("No news articles found. Make sure you have installed: pip install gnews duckduckgo-search")
        return []

    def _search_gnews(self, query: str) -> List[Dict[str, Any]]:
        try:
            google_news = GNews(
                language='en',
                country='US',
                max_results=self.max_articles,
                period=f"{self._days}d"
            )
            news = google_news.get_news(query)

            if not news:
                return []

            articles = []
            for item in news:
                article = {
                    "title": item.get('title', ''),
                    "url": item.get('url', ''),
                    "snippet": item.get('description', ''),
                    "date": item.get('published date', ''),
                    "source": item.get('publisher', {}).get('title', '')
                }
                articles.append(article)

            return articles
        except Exception as e:
            if self.verbose:
                self.logger.error(f"GNews error: {e}")
            return []

    def _search_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        try:
            time.sleep(random.uniform(1, 3))

            with DDGS() as ddgs:
                results = ddgs.text(
                    query + " news",
                    region='wt-wt',
                    max_results=self.max_articles,
                    timelimit=self.time_range
                )

                articles = []
                for result in results:
                    article = {
                        "title": result.get('title', ''),
                        "url": result.get('href', ''),
                        "snippet": result.get('body', ''),
                        "date": result.get('date', ''),
                        "source": result.get('source', '')
                    }
                    articles.append(article)

                return articles
        except Exception as e:
            if self.verbose:
                self.logger.error(f"DuckDuckGo error: {e}")
            return []
