import os
import requests
import datetime
import pytz
import yfinance as yf
import pandas as pd
import time
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === 設定 ===
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_detailed_market_data(is_morning):
    targets = {"NVDA": "NVIDIA", "^SOX": "半導体指数", "ES=F": "S&P500先物", "NQ=F": "ナスダック100先物"}
    report_data = ""
    for ticker, name in targets.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="10d")
            if len(hist) < 5: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            sma5 = hist['Close'].rolling(window=5).mean().iloc[-1]
            report_data += f"\n【{name} ({ticker})】\n- 現在値: {curr['Close']:.2f} ({change_pct:+.2f}%)\n- 5日線乖離: {((curr['Close']-sma5)/sma5)*100:+.2f}%\n"
        except: pass
    return report_data

def fetch_news_detailed():
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    start_date = (datetime.datetime.now(jst) - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    queries = ["NVIDIA AI", "US Stock Market", "US China Politics"]
    collected = ""
    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=start_date, page_size=4)
            for art in res.get('articles', []):
                collected += f"■{art['title']}\n{art.get('description','')[:200]}\n"
        except: pass
    return collected

def call_ai_with_fallback(prompt):
    """Geminiを優先し、エラーならLlamaに切り替える"""
    models = ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.3-70b-instruct:free"]
    for model in models:
        try:
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/my-stock-ai"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.8},
                timeout=180
            )
            data = res.json()
            if 'choices' in data:
                return data['choices'][0]['message']['content'], model
            print(f"{model} failed, trying next...")
            time.sleep(5)
        except: continue
    return None, None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    day = now.strftime('%A')
    is_morning = 5 <= now.hour <= 11
    market_info = get_detailed_market_data(is_morning)
    news_info = fetch_news_detailed()

    # モードと指示の構築（ユーザーの理想ロジックを継承）
    if day == "Sunday":
        mode = "日曜版：【今週の総括】全ニュースと値動きの徹底解剖"
        instruction = "1週間の全材料を振り返り、来週の戦略を4000文字以上の圧倒的ボリュームで解説してください。"
    elif is_morning:
        mode = "平日朝：【前夜の答え合わせ】予想の的中検証と要因分析"
        instruction = "昨夜の予測と実際の終値の的中判定、相場を動かした真の要因を分析せよ。"
    else:
        mode = "平日夕：【今夜のシナリオ予想】先物とテクニカルから読む展望"
        instruction = "先物の動きから今夜の開場シナリオを予測し、メイン・強気・弱気の3段階予想を提示せよ。"

    prompt = f"現在は2026/01/12です。米国株シニアストラテジストとして情熱的な5000文字級レポートを執筆せよ。\n【モード】{mode}\n【指示】{instruction}\n【データ】{market_info}\n【ニュース】{news_info}"

    report, used_model = call_ai_with_fallback(prompt)

    if report and DISCORD_WEBHOOK_URL:
        report += f"\n\n*(Model: {used_model})*"
        chunks = [report[i:i+1800] for i in range(0, len(report), 1800)]
        for i, chunk in enumerate(chunks):
            header = f"📊 **{mode} (Part {i+1}/{len(chunks)})**\n" if i == 0 else ""
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=header + chunk).execute()
            time.sleep(1)

if __name__ == "__main__":
    main()
