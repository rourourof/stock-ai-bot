import os
import requests
import datetime
import pytz
import yfinance as yf
import feedparser
import time
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# --- 1. ニュース取得（複数ソース） ---
def fetch_news_data():
    jst = pytz.timezone('Asia/Tokyo')
    start_date = (datetime.datetime.now(jst) - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    
    # ソースA: NewsAPI
    news_text = "【NewsAPI 事実情報】\n"
    try:
        api = NewsApiClient(api_key=os.getenv("NEWS_API_KEY"))
        res = api.get_everything(q="NVIDIA OR 'US Stock Market'", language='en', from_param=start_date, page_size=5)
        for art in res['articles']:
            news_text += f"- {art['publishedAt']}: {art['title']} ({art['source']['name']})\n"
    except: news_text += "取得失敗\n"

    # ソースB: Alpha Vantage (金融センチメント)
    news_text += "\n【AlphaVantage 金融センチメント情報】\n"
    try:
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=NVDA&apikey={os.getenv('AV_API_KEY')}"
        data = requests.get(url).json()
        for item in data.get('feed', [])[:5]:
            news_text += f"- {item['title']} (感応度: {item['overall_sentiment_label']})\n"
    except: news_text += "取得失敗\n"

    # ソースC: Google News (RSS速報)
    news_text += "\n【Google News 超速報】\n"
    try:
        feed = feedparser.parse("https://news.google.com/rss/search?q=NVIDIA+stock&hl=en-US&gl=US&ceid=US:en")
        for entry in feed.entries[:5]:
            news_text += f"- {entry.title}\n"
    except: news_text += "取得失敗\n"
    
    return news_text

# --- 2. 市場データ取得 ---
def get_market_info():
    nvda = yf.Ticker("NVDA")
    hist = nvda.history(period="5d")
    curr = hist.iloc[-1]
    prev = hist.iloc[-2]
    diff = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
    return f"NVIDIA: {curr['Close']:.2f}ドル ({diff:+.2f}%)"

# --- 3. メイン処理 ---
def main():
    jst = pytz.timezone('Asia/Tokyo')
    now_str = datetime.datetime.now(jst).strftime('%Y/%m/%d %H:%M')
    
    news_facts = fetch_news_data()
    market_facts = get_market_info()

    prompt = f"""
あなたは機関投資家向けの【事実確認専門】ストラテジストです。
本日: {now_str}

【厳守：ハルシネーション（創作）の禁止】
1. 以下の「事実データ」にない製品名、ニュース、出来事は絶対に書かないでください。
2. ニュースが不足している場合は、無理に内容を作らず、株価の数値分析のみを行ってください。
3. トーンは冷静、客観的、論理的に。

【提供された事実データ】
{news_facts}
【市場データ】
{market_facts}

構成:
1. 最新ファクトの要約（ニュース源を明記）
2. 数値的テクニカル分析
3. 事実に基づく今夜のシナリオ
"""

    # Geminiへの送信
    headers = {"Authorization": f"Bearer {os.getenv('GEMINI_API_KEY')}", "Content-Type": "application/json"}
    payload = {"model": "google/gemini-2.0-flash-exp:free", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0}
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload).json()
    report = response['choices'][0]['message']['content']

    # Discord送信
    DiscordWebhook(url=os.getenv("DISCORD_WEBHOOK_URL"), content=f"📑 **Factual Report ({now_str})**\n\n{report[:1900]}").execute()

if __name__ == "__main__":
    main()
