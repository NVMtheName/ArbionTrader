"""
Sentiment Analysis Module for Arbion Trading Platform
Provides FinBERT-powered financial sentiment analysis from news and social media sources.
"""

from sentiment.sentiment_engine import SentimentEngine
from sentiment.sentiment_aggregator import SentimentAggregator, SentimentSignal

__all__ = ['SentimentEngine', 'SentimentAggregator', 'SentimentSignal']
