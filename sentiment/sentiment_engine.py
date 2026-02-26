"""
Sentiment Engine - Core FinBERT-powered financial sentiment analyzer
Fetches news from Finnhub, Alpha Vantage, and Reddit; scores with ProsusAI/finbert.
Results are cached in Redis with a 15-minute TTL.
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

import requests

logger = logging.getLogger(__name__)

# FinBERT / transformers are heavy imports; lazy-load to keep startup fast
_finbert_pipeline = None


def _get_finbert_pipeline():
    """Lazy-load the FinBERT sentiment pipeline (ProsusAI/finbert)."""
    global _finbert_pipeline
    if _finbert_pipeline is None:
        try:
            from transformers import pipeline as hf_pipeline
            _finbert_pipeline = hf_pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert",
                tokenizer="ProsusAI/finbert",
                truncation=True,
                max_length=512,
            )
            logger.info("FinBERT model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load FinBERT model: {e}")
            raise
    return _finbert_pipeline


@dataclass
class SentimentResult:
    """Single scored text item."""
    text: str
    score: float          # -1.0 (bearish) to 1.0 (bullish)
    confidence: float     # 0.0 to 1.0
    source: str           # "finnhub", "alphavantage", "reddit"
    ticker: str
    timestamp: datetime


class SentimentEngine:
    """Fetches financial text from multiple sources and scores with FinBERT."""

    # Redis cache key prefix and TTL
    CACHE_PREFIX = "arbion_sentiment_"
    CACHE_TTL = 900  # 15 minutes

    def __init__(self):
        self.finnhub_key = os.environ.get("FINNHUB_API_KEY", "")
        self.alpha_vantage_key = os.environ.get("ALPHA_VANTAGE_KEY", "")

        # Redis via Flask-Caching (same pattern as MarketDataProvider)
        self._redis = None
        try:
            from app import cache
            self._redis = cache
            logger.info("Sentiment engine using Redis cache")
        except Exception:
            logger.warning("Redis cache unavailable for sentiment engine; results will not be cached")

        # PRAW Reddit client (lazy)
        self._reddit = None

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    def _cache_key(self, ticker: str, source: str) -> str:
        return f"{self.CACHE_PREFIX}{ticker}:{source}"

    def _get_cached(self, key: str) -> Optional[Any]:
        if self._redis is None:
            return None
        try:
            data = self._redis.get(key)
            return data
        except Exception as e:
            logger.debug(f"Cache read error: {e}")
            return None

    def _set_cache(self, key: str, data: Any) -> None:
        if self._redis is None:
            return
        try:
            self._redis.set(key, data, timeout=self.CACHE_TTL)
        except Exception as e:
            logger.debug(f"Cache write error: {e}")

    # ------------------------------------------------------------------
    # FinBERT scoring
    # ------------------------------------------------------------------
    def score_texts(self, texts: List[str]) -> List[Dict[str, float]]:
        """Score a batch of texts with FinBERT.

        Returns list of {"score": float, "confidence": float} dicts.
        FinBERT labels: positive, negative, neutral.
        We map to -1.0 .. 1.0 range.
        """
        if not texts:
            return []

        pipe = _get_finbert_pipeline()
        raw_results = pipe(texts, batch_size=16)

        scored = []
        for result in raw_results:
            label = result["label"].lower()
            conf = result["score"]
            if label == "positive":
                score = conf
            elif label == "negative":
                score = -conf
            else:  # neutral
                score = 0.0
            scored.append({"score": score, "confidence": conf})
        return scored

    def score_single(self, text: str) -> Dict[str, float]:
        """Score a single text."""
        results = self.score_texts([text])
        return results[0] if results else {"score": 0.0, "confidence": 0.0}

    # ------------------------------------------------------------------
    # Finnhub news
    # ------------------------------------------------------------------
    def fetch_finnhub_general_news(self, limit: int = 20) -> List[Dict]:
        """Fetch general financial news from Finnhub /api/v1/news."""
        cache_key = self._cache_key("_general", "finnhub_general")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if not self.finnhub_key:
            logger.warning("FINNHUB_API_KEY not set; skipping Finnhub general news")
            return []

        try:
            resp = requests.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": self.finnhub_key},
                timeout=10,
            )
            resp.raise_for_status()
            articles = resp.json()[:limit]
            self._set_cache(cache_key, articles)
            return articles
        except Exception as e:
            logger.error(f"Finnhub general news fetch failed: {e}")
            return []

    def fetch_finnhub_company_news(self, ticker: str, days_back: int = 2, limit: int = 20) -> List[Dict]:
        """Fetch company-specific news from Finnhub /api/v1/company-news."""
        cache_key = self._cache_key(ticker, "finnhub_company")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if not self.finnhub_key:
            logger.warning("FINNHUB_API_KEY not set; skipping Finnhub company news")
            return []

        try:
            date_to = datetime.utcnow().strftime("%Y-%m-%d")
            date_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            resp = requests.get(
                "https://finnhub.io/api/v1/company-news",
                params={
                    "symbol": ticker,
                    "from": date_from,
                    "to": date_to,
                    "token": self.finnhub_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            articles = resp.json()[:limit]
            self._set_cache(cache_key, articles)
            return articles
        except Exception as e:
            logger.error(f"Finnhub company news fetch failed for {ticker}: {e}")
            return []

    # ------------------------------------------------------------------
    # Alpha Vantage News Sentiment
    # ------------------------------------------------------------------
    def fetch_alpha_vantage_sentiment(self, ticker: str, limit: int = 20) -> List[Dict]:
        """Fetch news sentiment from Alpha Vantage NEWS_SENTIMENT endpoint."""
        cache_key = self._cache_key(ticker, "alphavantage")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if not self.alpha_vantage_key:
            logger.warning("ALPHA_VANTAGE_KEY not set; skipping Alpha Vantage sentiment")
            return []

        try:
            resp = requests.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "NEWS_SENTIMENT",
                    "tickers": ticker,
                    "limit": limit,
                    "apikey": self.alpha_vantage_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("feed", [])[:limit]
            self._set_cache(cache_key, articles)
            return articles
        except Exception as e:
            logger.error(f"Alpha Vantage sentiment fetch failed for {ticker}: {e}")
            return []

    # ------------------------------------------------------------------
    # Reddit (PRAW)
    # ------------------------------------------------------------------
    def _get_reddit_client(self):
        """Lazy-initialise the PRAW Reddit client."""
        if self._reddit is not None:
            return self._reddit

        try:
            import praw
            client_id = os.environ.get("REDDIT_CLIENT_ID", "")
            client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
            user_agent = os.environ.get("REDDIT_USER_AGENT", "ArbionTrader/1.0")

            if not client_id or not client_secret:
                logger.warning("Reddit API credentials not set; skipping Reddit sentiment")
                return None

            self._reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            logger.info("PRAW Reddit client initialised")
            return self._reddit
        except Exception as e:
            logger.error(f"Failed to initialise Reddit client: {e}")
            return None

    def fetch_reddit_posts(self, ticker: str, subreddits: Optional[List[str]] = None,
                           limit: int = 15) -> List[Dict]:
        """Fetch recent Reddit posts mentioning a ticker."""
        cache_key = self._cache_key(ticker, "reddit")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        reddit = self._get_reddit_client()
        if reddit is None:
            return []

        if subreddits is None:
            subreddits = ["wallstreetbets", "stocks", "cryptocurrency"]

        posts: List[Dict] = []
        for sub_name in subreddits:
            try:
                subreddit = reddit.subreddit(sub_name)
                for submission in subreddit.search(ticker, sort="new", time_filter="day", limit=limit):
                    posts.append({
                        "title": submission.title,
                        "selftext": (submission.selftext or "")[:500],
                        "score": submission.score,
                        "num_comments": submission.num_comments,
                        "subreddit": sub_name,
                        "created_utc": submission.created_utc,
                    })
            except Exception as e:
                logger.error(f"Reddit fetch failed for r/{sub_name}: {e}")

        self._set_cache(cache_key, posts)
        return posts

    # ------------------------------------------------------------------
    # Unified analysis per ticker
    # ------------------------------------------------------------------
    def analyze_ticker(self, ticker: str) -> Dict[str, Any]:
        """Run full sentiment analysis for a single ticker.

        Returns {
            "ticker": str,
            "score": float,          # normalised -1.0 .. 1.0
            "confidence": float,     # 0.0 .. 1.0
            "sources": { "finnhub": [...], "alphavantage": [...], "reddit": [...] },
            "details": [ SentimentResult ... ],
            "timestamp": str (ISO)
        }
        """
        # Check top-level cache
        top_cache_key = self._cache_key(ticker, "full_analysis")
        cached = self._get_cached(top_cache_key)
        if cached is not None:
            return cached

        all_results: List[SentimentResult] = []

        # --- Finnhub (company-specific + general mentioning ticker) ---
        finnhub_articles = self.fetch_finnhub_company_news(ticker)
        finnhub_general = self.fetch_finnhub_general_news()
        # Filter general news that mentions the ticker
        ticker_lower = ticker.lower()
        relevant_general = [
            a for a in finnhub_general
            if ticker_lower in (a.get("headline", "") + " " + a.get("summary", "")).lower()
        ]
        finnhub_texts = []
        for a in finnhub_articles + relevant_general:
            text = a.get("headline", "") or a.get("summary", "")
            if text:
                finnhub_texts.append(text)

        if finnhub_texts:
            scores = self.score_texts(finnhub_texts)
            for text, scored in zip(finnhub_texts, scores):
                all_results.append(SentimentResult(
                    text=text[:200],
                    score=scored["score"],
                    confidence=scored["confidence"],
                    source="finnhub",
                    ticker=ticker,
                    timestamp=datetime.utcnow(),
                ))

        # --- Alpha Vantage ---
        av_articles = self.fetch_alpha_vantage_sentiment(ticker)
        av_texts = []
        for a in av_articles:
            text = a.get("title", "") or a.get("summary", "")
            if text:
                av_texts.append(text)

        if av_texts:
            scores = self.score_texts(av_texts)
            for text, scored in zip(av_texts, scores):
                all_results.append(SentimentResult(
                    text=text[:200],
                    score=scored["score"],
                    confidence=scored["confidence"],
                    source="alphavantage",
                    ticker=ticker,
                    timestamp=datetime.utcnow(),
                ))

        # --- Reddit ---
        reddit_posts = self.fetch_reddit_posts(ticker)
        reddit_texts = []
        for p in reddit_posts:
            text = p.get("title", "")
            body = p.get("selftext", "")
            combined = f"{text}. {body}" if body else text
            if combined:
                reddit_texts.append(combined)

        if reddit_texts:
            scores = self.score_texts(reddit_texts)
            for text, scored in zip(reddit_texts, scores):
                all_results.append(SentimentResult(
                    text=text[:200],
                    score=scored["score"],
                    confidence=scored["confidence"],
                    source="reddit",
                    ticker=ticker,
                    timestamp=datetime.utcnow(),
                ))

        # --- Aggregate ---
        if all_results:
            weighted_sum = sum(r.score * r.confidence for r in all_results)
            total_confidence = sum(r.confidence for r in all_results)
            overall_score = weighted_sum / total_confidence if total_confidence > 0 else 0.0
            overall_confidence = total_confidence / len(all_results)
        else:
            overall_score = 0.0
            overall_confidence = 0.0

        # Group by source for the response
        sources = {"finnhub": [], "alphavantage": [], "reddit": []}
        for r in all_results:
            sources.setdefault(r.source, []).append({
                "text": r.text,
                "score": round(r.score, 4),
                "confidence": round(r.confidence, 4),
            })

        result = {
            "ticker": ticker,
            "score": round(max(-1.0, min(1.0, overall_score)), 4),
            "confidence": round(min(1.0, overall_confidence), 4),
            "sources": sources,
            "sources_count": len(all_results),
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._set_cache(top_cache_key, result)
        return result

    def analyze_tickers(self, tickers: List[str]) -> Dict[str, Dict]:
        """Analyze multiple tickers. Returns {ticker: analysis_dict}."""
        results = {}
        for ticker in tickers:
            results[ticker] = self.analyze_ticker(ticker.upper())
        return results
