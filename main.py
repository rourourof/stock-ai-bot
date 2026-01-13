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
            report_data += f"\n【{name} ({ticker})】\n- 終値/現在値: {curr['Close']:.2f} ({change_pct:+.2f}%)\n- 5日移動平均乖離率: {((curr['Close']-sma5)/sma5)*100:+.2f}%\n"
        except: pass
    return report_data

def fetch_news_by_range(days):
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    start_date = (datetime.datetime.now(jst) - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    queries = ["NVIDIA AI", "US Stock Market", "Semiconductor Industry"]
    collected = ""
    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=start_date, page_size=6)
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
    # 正確性を期すためtemperatureは0.3
    payload = {"model": "google/gemini-2.0-flash-exp:free", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
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
    # 実行時の日付と時刻を動的に取得
    current_time = now.strftime('%Y/%m/%d %H:%M')
    is_morning = 5 <= now.hour <= 11
    
    market_info = get_detailed_market_data()
    news_weekly = fetch_news_by_range(7) 
    news_latest = fetch_news_by_range(2) 

    # プロンプト内の日付も変数(current_time)を使用するように変更
    prompt = f"""
あなたは機関投資家向けのシニアストラテジストです。
【本日の日付: {current_time} (JST)】

【厳守事項：事実に基づいた分析】
- 過去の学習データ（2024年以前）に依拠せず、提供された最新データのみを用いて執筆してください。
- 現在は2026年です。2024年や2025年の出来事を「最新ニュース」として扱うことは重大な誤報と見なします。
- 提供されたニュースソースに存在しない製品発表や数値を捏造することは厳禁です。
- 冷静で論理的な専門用語を使用してください。

【1. 週次マクロ環境（直近1週間の背景）】:
{news_weekly}

【2. 最新の市場動向（直近48時間の主要材料）】:
{news_latest}

【3. 株価・指数データ】:
{market_info}

【構成要件】:
1. **マクロ背景と重要ニュース格付け**：今週の流れを整理。
2. **最新材料のインパクト評価**：直近ニュースが短期需給に与える影響。
3. **NVIDIA & 半導体セクター分析**：数値に基づいた分析。
4. **{'本日の市場総括' if is_morning else '今夜のマーケットシナリオ予測'}**：メイン・強気・弱気の3区分。
5. **ニュースソース（日本時間日時付き）**

ルール：4000〜5000文字程度の詳密なレポート。正確性を最優先し、事実に即した洞察を行うこと。
"""

    report = call_gemini(prompt)

    if report and DISCORD_WEBHOOK_URL:
        chunks = [report[i:i+1900] for i in range(0, len(report), 1800)]
        for i, chunk in enumerate(chunks):
            # タイトルの日付も自動更新
            header = f"📑 **US Market Strategy Report ({current_time}) P{i+1}**\n" if i == 0 else ""
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=header + chunk).execute()
            time.sleep(2)

if __name__ == "__main__":
    main()
