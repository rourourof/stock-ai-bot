import os
import requests
import datetime
import pytz
import yfinance as yf
import time
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === 設定 ===
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_data():
    targets = {"NVDA": "NVIDIA", "^SOX": "半導体指数", "ES=F": "S&P500先物", "NQ=F": "ナスダック100先物"}
    report_data = ""
    for ticker, name in targets.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if len(hist) < 2: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            report_data += f"\n【{name}】価格: {curr['Close']:.2f} ({change_pct:+.2f}%)\n"
        except: pass
    return report_data

def fetch_news():
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    three_days_ago = (datetime.datetime.now(jst) - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
    collected = ""
    for q in ["NVIDIA AI", "US Market"]:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=three_days_ago, page_size=3)
            for art in res.get('articles', []):
                collected += f"■{art['title']}\n{art.get('description','')[:200]}\n\n"
        except: pass
    return collected

def call_ai(prompt):
    """確実に回答を得るための共通関数"""
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=120
        )
        return res.json()['choices'][0]['message']['content']
    except:
        return "（このセクションの生成に失敗しました）"

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    is_morning = 5 <= now.hour <= 11
    market_info = get_market_data()
    news_info = fetch_news()

    # --- セクション1: ニュース分析とランキング ---
    prompt1 = f"今日は{now.strftime('%Y/%m/%d')}です。最新ニュースから市場影響度ランキングを2000文字以上で詳細に解説せよ。絵文字多用。\n{news_info}"
    part1 = call_ai(prompt1)
    time.sleep(20) # 制限回避

    # --- セクション2: NVIDIA & 半導体・政治・AI ---
    prompt2 = f"NVIDIAと半導体指数のテクニカル分析、および米国政治・AI・対中政策の動向を別枠で2000文字以上で執筆せよ。\n{market_info}"
    part2 = call_ai(prompt2)
    time.sleep(20)

    # --- セクション3: 答え合わせ または 予想 ---
    mode = "【朝の答え合わせと要因分析】" if is_morning else "【夕方の今夜シナリオ予想】"
    prompt3 = f"{mode}を2000文字以上で執筆せよ。無視された材料や先物動向を深く論じること。\n{market_info}"
    part3 = call_ai(prompt3)

    full_report = f"📊 **US Market Professional Report**\n\n{part1}\n\n{part2}\n\n{part3}"

    if DISCORD_WEBHOOK_URL:
        chunks = [full_report[i:i+1800] for i in range(0, len(full_report), 1800)]
        for chunk in chunks:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": chunk})
            time.sleep(1)

if __name__ == "__main__":
    main()
