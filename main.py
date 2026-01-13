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

def fetch_news_by_range(days):
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    start_date = (datetime.datetime.now(jst) - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    queries = ["NVIDIA", "US stock market", "FED interest rate", "Semiconductor"]
    collected = ""
    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=start_date, page_size=5)
            for art in res.get('articles', []):
                utc_dt = datetime.datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
                jst_dt = utc_dt.astimezone(jst)
                date_str = jst_dt.strftime('%m/%d %H:%M')
                collected += f"■{date_str}(JST) {art['title']}: {art.get('description','')[:150]}\n"
        except: pass
    return collected

def call_gemini(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/my-stock-ai"}
    payload = {"model": "google/gemini-2.0-flash-exp:free", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2} # さらに正確性重視
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
    # 毎日自動で変わる日付
    current_time = now.strftime('%Y/%m/%d %H:%M')
    is_morning = 5 <= now.hour <= 11
    
    market_info = get_detailed_market_data()
    news_weekly = fetch_news_by_range(7) 
    news_latest = fetch_news_by_range(2) 

    prompt = f"""
あなたは機関投資家向けのシニアストラテジストです。
【本日の日付: {current_time} (JST)】

【最重要：分析の優先順位】
1. 【直近48時間の主要ニュース】を分析のメイン材料とし、現在の市場心理（センチメント）を解き明かしてください。数値の変動（先物など）は、そのニュースの結果として解釈してください。
2. 2026年の最新事実にのみ基づき、過去（2024/2025年）の出来事を「今起きたこと」のように扱う誤報は絶対に避けてください。
3. 冷静かつ論理的なトーンを維持し、根拠のない予測（ハルシネーション）を厳禁します。

【提供データ】
■直近48時間の超最新ニュース（メイン材料）:
{news_latest}

■直近1週間のマクロ背景:
{news_weekly}

■市場数値データ:
{market_info}

【構成要件】:
1. **直近48時間の主要材料とインパクト評価**：最新ニュースを深掘りし、短期需給への影響を論理的に評価。
2. **マクロ背景と重要ニュース格付け**：1週間の流れを整理。
3. **NVIDIA & 半導体セクター分析**：ニュースと数値（移動平均乖離等）を組み合わせた冷徹な分析。
4. **{'本日の市場総括' if is_morning else '今夜のマーケットシナリオ予測'}**：論理的な3区分（メイン・強気・弱気）。
5. **ニュースソース（日本時間日時付き）**

ルール：4000文字以上の詳密なレポート。事実に即した深い洞察を行うこと。
"""

    report = call_gemini(prompt)

    if report and DISCORD_WEBHOOK_URL:
        chunks = [report[i:i+1900] for i in range(0, len(report), 1800)]
        for i, chunk in enumerate(chunks):
            header = f"📑 **Institutional Strategy Report ({current_time}) P{i+1}**\n" if i == 0 else ""
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=header + chunk).execute()
            time.sleep(2)

if __name__ == "__main__":
    main()
