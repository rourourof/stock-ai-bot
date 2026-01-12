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
            report_data += f"- {name}: {curr['Close']:.2f} ({change_pct:+.2f}%)\n"
        except: pass
    return report_data

def fetch_news():
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    three_days_ago = (datetime.datetime.now(jst) - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
    collected = ""
    for q in ["NVIDIA AI", "US Stock Market"]:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=three_days_ago, page_size=2)
            for art in res.get('articles', []):
                collected += f"■{art['title']}\n{art.get('description','')[:150]}\n"
        except: pass
    return collected

def call_ai(prompt):
    """リトライ機能を備えたAI呼び出し"""
    for i in range(2): # 失敗しても1度だけ自動リトライ
        try:
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/my-stock-ai"},
                json={
                    "model": "google/gemini-2.0-flash-exp:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                },
                timeout=90
            )
            data = res.json()
            if 'choices' in data:
                return data['choices'][0]['message']['content']
            else:
                print(f"Error: {data}")
                time.sleep(40) # 失敗した場合は長めに待機
        except Exception as e:
            print(f"Exception: {e}")
            time.sleep(40)
    return "（このセクションは現在AIが混雑しており取得できませんでした。時間をおいて再実行してください）"

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    is_morning = 5 <= now.hour <= 11
    market_info = get_market_data()
    news_info = fetch_news()

    # --- セクション1: ニュース分析 (文字数指示をマイルドに) ---
    prompt1 = f"プロの米国株アナリストとして、最新ニュースから市場影響度ランキングを解説せよ。各項目を非常に詳しく、絵文字を使い情熱的に書くこと。日付は{now.strftime('%Y/%m/%d')}。情報：\n{news_info}"
    part1 = call_ai(prompt1)
    time.sleep(45) # 無料枠のレート制限回避のため長めに待機

    # --- セクション2: NVIDIA・政治・AI ---
    prompt2 = f"NVIDIAと半導体指数のテクニカル分析、および米国政治・AI・対中政策の動向をプロの視点で別枠を設けて詳しく執筆せよ。\n{market_info}"
    part2 = call_ai(prompt2)
    time.sleep(45)

    # --- セクション3: 答え合わせ または 予想 ---
    mode = "朝の答え合わせと要因分析" if is_morning else "夕方の今夜シナリオ予想"
    prompt3 = f"米国株アナリストとして、現在のデータから【{mode}】を執筆せよ。無視された材料や先物の動きを深く鋭く論じること。\n{market_info}"
    part3 = call_ai(prompt3)

    full_report = f"📊 **US Market Strategy Report**\n\n{part1}\n\n{part2}\n\n{part3}"

    if DISCORD_WEBHOOK_URL:
        chunks = [full_report[i:i+1800] for i in range(0, len(full_report), 1800)]
        for chunk in chunks:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": chunk})
            time.sleep(2)

if __name__ == "__main__":
    main()
