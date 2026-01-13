import os
import requests
import datetime
import pytz
import yfinance as yf
import feedparser
import time
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === 設定 ===
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AV_API_KEY = os.getenv("AV_API_KEY") # Alpha Vantage追加
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_detailed_market_data():
    targets = {"NVDA": "NVIDIA", "^SOX": "半導体指数", "ES=F": "S&P500先物", "NQ=F": "ナスダック100先物"}
    report_data = ""
    for ticker, name in targets.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="10d")
            if len(hist) < 2: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            sma5 = hist['Close'].rolling(window=5).mean().iloc[-1]
            report_data += f"\n【{name} ({ticker})】\n- 価格: {curr['Close']:.2f} ({change_pct:+.2f}%)\n- 5日線乖離率: {((curr['Close']-sma5)/sma5)*100:+.2f}%\n"
        except: pass
    return report_data

def fetch_multi_source_news():
    jst = pytz.timezone('Asia/Tokyo')
    start_date = (datetime.datetime.now(jst) - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    collected = ""

    # 1. NewsAPI (主要メディア)
    try:
        newsapi = NewsApiClient(api_key=NEWS_API_KEY)
        queries = ["NVIDIA 2026", "US stock market 2026"]
        for q in queries:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=start_date, page_size=5)
            for art in res.get('articles', []):
                if any(src in art['source']['name'] for src in ["Yahoo", "Reuters", "Bloomberg", "Wall Street Journal"]):
                    collected += f"■[NewsAPI] {art['source']['name']}: {art['title']}\n"
    except: pass

    # 2. Alpha Vantage (金融センチメント分析)
    try:
        if AV_API_KEY:
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=NVDA&apikey={AV_API_KEY}"
            data = requests.get(url, timeout=15).json()
            for item in data.get('feed', [])[:5]:
                sentiment = item.get('overall_sentiment_label', 'Neutral')
                collected += f"■[AlphaVantage] {item['title']} (市場心理: {sentiment})\n"
    except: pass

    # 3. Google News RSS (超速報)
    try:
        feed = feedparser.parse("https://news.google.com/rss/search?q=NVIDIA+stock+2026&hl=en-US&gl=US&ceid=US:en")
        for entry in feed.entries[:5]:
            collected += f"■[GoogleNews] {entry.title}\n"
    except: pass

    return collected

def call_gemini(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/my-stock-ai"}
    payload = {
        "model": "google/gemini-2.0-flash-exp:free", 
        "messages": [{"role": "user", "content": prompt}], 
        "temperature": 0.0 
    }
    for attempt in range(3):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=180)
            data = res.json()
            if 'choices' in data: return data['choices'][0]['message']['content']
            time.sleep(30) 
        except: time.sleep(30)
    return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    current_time = now.strftime('%Y/%m/%d %H:%M')
    is_morning = 5 <= now.hour <= 11
    
    market_info = get_detailed_market_data()
    news_all = fetch_multi_source_news()

    prompt = f"""
あなたは機関投資家向けレポートを作成する【事実確認専門】のストラテジストです。
現在は【{current_time}】です。

【鉄の掟：ハルシネーションの禁止】
1. 下記の「実在ニュースデータ」に記載されていない情報は、絶対にレポートに含めないでください。
2. 「仮定のニュース」や「サンプルデータ」といった言葉は一切使わず、提供された情報のみを整理してください。
3. ニュースが不足している場合は、無理に内容を膨らませず、数値データのテクニカル分析を重点的に行ってください。

【市場数値データ】
{market_info}

【提供された実在ニュースソース（直近48時間）】
{news_all}

【レポート構成】:
1. **重要ファクトの抽出と評価**：各ソース（NewsAPI, AlphaVantage, GoogleNews）から事実を整理。
2. **NVIDIA & 半導体セクター数値分析**：価格、移動平均乖離率を用いた客観的分析。
3. **{'市場総括' if is_morning else '今夜のシナリオ予想'}**：メイン・強気・弱気の3区分。

トーン：冷徹、客観的、簡潔。
"""

    report = call_gemini(prompt)

    if report and DISCORD_WEBHOOK_URL:
        chunks = [report[i:i+1900] for i in range(0, len(report), 1900)]
        for i, chunk in enumerate(chunks):
            header = f"📑 **Fact-Based Strategy Report ({current_time}) P{i+1}**\n" if i == 0 else ""
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=header + chunk).execute()
            time.sleep(2)

if __name__ == "__main__":
    main()
