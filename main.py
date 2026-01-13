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
AV_API_KEY = os.getenv("AV_API_KEY")
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

    # 1. NewsAPI
    if NEWS_API_KEY:
        try:
            newsapi = NewsApiClient(api_key=NEWS_API_KEY)
            res = newsapi.get_everything(q="NVIDIA 2026", language='en', sort_by='publishedAt', from_param=start_date, page_size=5)
            for art in res.get('articles', []):
                collected += f"■[NewsAPI] {art['source']['name']}: {art['title']}\n"
        except: print("NewsAPI取得に失敗しました")

    # 2. Alpha Vantage
    if AV_API_KEY:
        try:
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=NVDA&apikey={AV_API_KEY}"
            data = requests.get(url, timeout=15).json()
            for item in data.get('feed', [])[:5]:
                sentiment = item.get('overall_sentiment_label', 'Neutral')
                collected += f"■[AlphaVantage] {item['title']} ({sentiment})\n"
        except: print("AlphaVantage取得に失敗しました")

    # 3. Google News RSS
    try:
        feed = feedparser.parse("https://news.google.com/rss/search?q=NVIDIA+stock+2026&hl=en-US&gl=US&ceid=US:en")
        for entry in feed.entries[:5]:
            collected += f"■[GoogleNews] {entry.title}\n"
    except: print("GoogleNews取得に失敗しました")

    return collected

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    current_time = now.strftime('%Y/%m/%d %H:%M')
    
    # URLチェック（ログに出力）
    if not DISCORD_WEBHOOK_URL:
        print("エラー: DISCORD_WEBHOOK_URL が設定されていません。GitHub Secretsを確認してください。")
    
    market_info = get_detailed_market_data()
    news_all = fetch_multi_source_news()

    prompt = f"あなたは機関投資家向けストラテジストです。現在:{current_time}\n【市場データ】\n{market_info}\n【ニュース】\n{news_all}\n上記を元に、事実のみを整理したレポートを4000文字程度で作成してください。"

    # Gemini呼び出し
    report = None
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "google/gemini-2.0-flash-exp:free", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0}
    
    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=120)
        data = res.json()
        if 'choices' in data:
            report = data['choices'][0]['message']['content']
            # デバッグ用：レポートの最初の100文字をログに表示
            print(f"レポート作成成功: {report[:100]}...")
        else:
            print(f"Geminiエラー応答: {data}")
    except Exception as e:
        print(f"Gemini通信エラー: {e}")

    # Discord送信
    if report and DISCORD_WEBHOOK_URL:
        try:
            chunks = [report[i:i+1900] for i in range(0, len(report), 1900)]
            for i, chunk in enumerate(chunks):
                header = f"📑 **Fact-Based Report ({current_time}) P{i+1}**\n" if i == 0 else ""
                webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=header + chunk)
                response = webhook.execute()
                print(f"Discord送信ステータス (P{i+1}): {response}")
                time.sleep(1)
        except Exception as e:
            print(f"Discord送信エラー: {e}")
    else:
        print("レポートまたはWebhook URLが空のため、Discord送信をスキップしました。")

if __name__ == "__main__":
    main()
