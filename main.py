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
            report_data += f"\n【{name} ({ticker})】\n- 現在値: {curr['Close']:.2f} ({change_pct:+.2f}%)\n- 5日線乖離: {((curr['Close']-sma5)/sma5)*100:+.2f}%\n"
        except: pass
    return report_data

def fetch_news_by_range(days):
    """指定された日数範囲のニュースを取得"""
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    start_date = (datetime.datetime.now(jst) - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    
    queries = ["NVIDIA AI", "US Stock Market", "Semiconductor"]
    collected = ""
    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=start_date, page_size=5)
            for art in res.get('articles', []):
                utc_dt = datetime.datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
                jst_dt = utc_dt.astimezone(jst)
                date_str = jst_dt.strftime('%Y/%m/%d %H:%M')
                collected += f"■日時: {date_str} (JST)\nTITLE: {art['title']}\nDETAIL: {art.get('description','')[:150]}\n\n"
        except: pass
    return collected

def call_gemini(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/my-stock-ai"}
    payload = {"model": "google/gemini-2.0-flash-exp:free", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}

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
    current_date_str = now.strftime('%Y/%m/%d %H:%M')
    is_morning = 5 <= now.hour <= 11
    
    market_info = get_detailed_market_data()
    # ニュースを2種類の期間で取得
    news_weekly = fetch_news_by_range(7) # 1週間分の背景
    news_latest = fetch_news_by_range(2) # 2日間の超最新

    mode = "朝：【答え合わせと週間展望】" if is_morning else "夕：【今夜のシナリオと週間トレンド】"

    prompt = f"""
【鉄の掟：過去情報の完全排除】
現在は【2026/01/13 {current_date_str}】です。
あなたの記憶にある2024年や2025年の出来事は「歴史」であり、現在の材料ではありません。
もし「2024年のAIバブル当初は〜」といった古い話を「現在のニュース」として混ぜた場合、このレポートは失格となります。
提供された「2026年1月」のデータのみを使用してください。

あなたはシニアストラテジストとして、5000文字級の重厚な日本語レポートを作成してください。

【1. 今週一週間のマクロ背景（株価に影響を与えている継続材料）】:
{news_weekly}

【2. 直近2日間の超最新ニュース（今すぐ動くべき材料）】:
{news_latest}

【3. 市場数値データ】:
{market_info}

【必須構成】:
1. **今週の影響度格付けランキング**：1週間を通じた大きな流れを整理。
2. **最新24-48時間のインパクト分析**：直近ニュースが今夜どう爆発するか。
3. **NVIDIA & 半導体 集中講義**：テクニカルと最新材料の融合。
4. **【重要】{'朝の的中判定' if is_morning else '今夜の3大シナリオ'}**
5. **ニュースソース一覧（日時付き）**

【執筆ルール】：
- 絵文字を多用し、投資家を鼓舞する熱量で。
- 10分かけて読むボリューム（5000文字）を死守せよ。
- すべての情報を「2026年現在の視点」で語れ。
"""

    report = call_gemini(prompt)

    if report and DISCORD_WEBHOOK_URL:
        chunks = [report[i:i+1800] for i in range(0, len(report), 1800)]
        for i, chunk in enumerate(chunks):
            header = f"🚀 **US Strategy Report ({current_date_str}) Part {i+1}**\n" if i == 0 else ""
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=header + chunk).execute()
            time.sleep(2)

if __name__ == "__main__":
    main()
