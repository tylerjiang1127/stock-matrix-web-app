import requests
import os
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

def test_news_sentiment(ticker="AAPL"):
    """Test Alpha Vantage NEWS_SENTIMENT API"""
    
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker,
        "apikey": api_key,
        "limit": 10,  # Number of articles to fetch
        "sort": "LATEST"  # or "RELEVANCE"
    }
    
    print(f"Fetching news sentiment for {ticker}...")
    response = requests.get(url, params=params, timeout=30)
    data = response.json()
    
    # Check for errors
    if "Error Message" in data:
        print(f"Error: {data['Error Message']}")
        return
    
    if "Note" in data or "Information" in data:
        print(f"Rate limit: {data.get('Note') or data.get('Information')}")
        return
    
    # Print overall sentiment
    print("\n" + "="*60)
    print(f"📊 NEWS SENTIMENT FOR {ticker}")
    print("="*60)
    
    # Check if we have the expected data structure
    if "feed" not in data:
        print("Unexpected response structure:")
        pprint(data)
        return
    
    # Overall stats
    print(f"\n📈 Total articles found: {data.get('items', 'N/A')}")
    print(f"🎯 Sentiment score model: {data.get('sentiment_score_definition', 'N/A')}")
    
    # Process each article
    print("\n📰 RECENT NEWS ARTICLES:")
    print("-"*60)
    
    for i, article in enumerate(data.get("feed", [])[:5], 1):  # Show first 5
        title = article.get("title", "No title")
        source = article.get("source", "Unknown")
        time_published = article.get("time_published", "Unknown")
        overall_sentiment = article.get("overall_sentiment_label", "N/A")
        overall_score = article.get("overall_sentiment_score", 0)
        
        print(f"\n{i}. {title[:80]}...")
        print(f"   📍 Source: {source}")
        print(f"   🕐 Published: {time_published}")
        print(f"   💭 Sentiment: {overall_sentiment} (score: {overall_score})")
        
        # Get ticker-specific sentiment
        ticker_sentiments = article.get("ticker_sentiment", [])
        for ts in ticker_sentiments:
            if ts.get("ticker") == ticker:
                print(f"   🎯 {ticker} Relevance: {ts.get('relevance_score', 'N/A')}")
                print(f"   🎯 {ticker} Sentiment: {ts.get('ticker_sentiment_label', 'N/A')} ({ts.get('ticker_sentiment_score', 'N/A')})")
    
    # Summary: Calculate average sentiment
    print("\n" + "="*60)
    print("📊 SENTIMENT SUMMARY")
    print("="*60)
    
    all_scores = []
    for article in data.get("feed", []):
        for ts in article.get("ticker_sentiment", []):
            if ts.get("ticker") == ticker:
                score = ts.get("ticker_sentiment_score")
                if score:
                    all_scores.append(float(score))
    
    if all_scores:
        avg_score = sum(all_scores) / len(all_scores)
        print(f"\n🎯 Average {ticker} Sentiment Score: {avg_score:.4f}")
        
        if avg_score >= 0.35:
            print("   📈 Overall: BULLISH")
        elif avg_score >= 0.15:
            print("   📊 Overall: SOMEWHAT BULLISH")
        elif avg_score >= -0.15:
            print("   ⚖️ Overall: NEUTRAL")
        elif avg_score >= -0.35:
            print("   📉 Overall: SOMEWHAT BEARISH")
        else:
            print("   🔻 Overall: BEARISH")
    
    return data


if __name__ == "__main__":
    # Test with different tickers
    test_news_sentiment("AAPL")
    
    # Uncomment to test other tickers:
    # test_news_sentiment("TSLA")
    # test_news_sentiment("NVDA")