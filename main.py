import os
import requests
import datetime
import pytz
import yfinance as yf
import feedparser
import time
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# ==========================================
# 1. ニュース取得セクション（3つのソースから取得）
# ==========================================

def fetch_all_news():
    jst = pytz.timezone('Asia/Tokyo')
    # 直近2日間の情報をターゲットにする
    start_date = (datetime.datetime.now(jst) - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    
    news_content = ""

    # --- ソースA: NewsAPI (主要メディア) ---
    try:
        api_key = os.getenv("NEWS_API_KEY")
        if api_key:
            newsapi = NewsApiClient(api_key=api_key)
            # NVIDIAおよび米国市場に関する最新記事を取得
            res = newsapi.get_everything(q="NVIDIA OR 'US Stock Market'", language='en', from_param=start_date, sort_by='publishedAt', page_size=8)
            news_content += "\n【NewsAPI: 主要メディア速報】\n"
            for art in res.get('articles', []):
                news_content += f"- {art['publishedAt']} | {art['source']['name']}: {art['title']}\n"
    except Exception as e:
        news_content += f"\n【NewsAPI】取得エラー: {e}\n"

    # --- ソースB: Alpha Vantage (金融センチメント分析) ---
    try:
        av_key = os.getenv("AV_API_KEY")
        if av_key:
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=NVDA&apikey={av_key}"
            r = requests.get(url, timeout=15)
            data = r.json()
            news_content += "\n【AlphaVantage: 投資家心理/センチメント】\n"
            # 上位5件のセンチメント付きニュースを抽出
            for item in data.get('feed', [])[:5]:
                sentiment = item.get('overall_sentiment_label', '不明')
                news_content += f"- {item['title']} (市場心理: {sentiment})\n"
    except Exception as e:
        news_content += f"\n【AlphaVantage】取得エラー: {e}\n"

    # --- ソースC: Google News (RSS/超速報) ---
    try:
        news_content += "\n【Google News: リアルタイム検索結果】\n"
        # 英語圏の最新情報を取得
        feed = feedparser.parse("https://news.google.com/rss/search?q=NVIDIA+stock+2026&hl=en-US&gl=US&ceid=US:en")
        for entry in feed.entries[:6]:
            news_content += f"- {entry.published} | {entry.title}\n"
    except Exception as e:
        news_content += f"\n【Google News】取得エラー: {e}\n"

    return news_content

# ==========================================
# 2. 市場数値データ取得セクション
# ==========================================

def get_market_summary():
    try:
        # NVIDIAと主要指数の現在値を取得
        tickers = {"NVDA": "NVIDIA", "^SOX": "半導体指数", "ES=F": "S&P500先物"}
        summary = "\n【リアルタイム市場数値】\n"
        for sym, name in tickers.items():
            t = yf.Ticker(sym)
            h = t.history(period="5d")
            if len(h) < 2: continue
            curr = h.iloc[-1]['Close']
            prev = h.iloc[-2]['Close']
            diff = ((curr - prev) / prev) * 100
            summary += f"- {name}: {curr:.2f} ({diff:+.2f}%)\n"
        return summary
    except:
        return "\n【市場数値】取得失敗\n"

# ==========================================
# 3. AI（Gemini）レポート作成 & 送信
# ==========================================

def main():
    # 日本時間の取得
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    date_str = now.strftime('%Y/%m/%d %H:%M')

    # 各種データの収集
    factual_news = fetch_all_news()
    market_data = get_market_summary()

    # AIへの指示（プロンプト）
    # temperature=0.0 により、提供データ以外の「嘘」を完全に封じる
    prompt = f"""
あなたは機関投資家向けの【事実確認専門】ストラテジストです。
本日: {date_str}

【厳守：ハルシネーション（創作・仮説）の禁止】
1. 下記の「実在ニュースデータ」および「市場数値」に記載されていない情報は、絶対にレポートに含めないでください。
2. ニュースが不足している場合は、無理に内容を作らず、「特筆すべき新規ニュースなし」と事実を述べてください。
3. 2024年や2025年の出来事を現在のニュースとして扱わないでください。

【提供された実在ニュースデータ】
{factual_news}

【提供された市場数値データ】
{market_data}

構成（冷静、客観的なトーンで執筆せよ）:
1. 主要ニュースのファクト要約（どのソースからの情報か明記）
2. 市場数値のテクニカル分析（乖離率や騰落）
3. 事実に基づく今夜のマーケット見通し（論理的なシナリオ）
"""

    # Gemini APIへのリクエスト（OpenRouter経由）
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("APIキーが設定されていません。")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=120)
        report = response.json()['choices'][0]['message']['content']

        # Discordへ送信
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if webhook_url:
            # 長文対策で分割送信
            chunks = [report[i:i+1800] for i in range(0, len(report), 1800)]
            for i, chunk in enumerate(chunks):
                title = f"📑 **Institutional Daily Report ({date_str}) P{i+1}**\n" if i == 0 else ""
                DiscordWebhook(url=webhook_url, content=title + chunk).execute()
                time.sleep(1)
        else:
            print(report)
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
