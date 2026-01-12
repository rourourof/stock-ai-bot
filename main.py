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

# 無料で最も賢く、最新情報を扱えるLlama 3.3を指定
MODEL = "meta-llama/llama-3.3-70b-instruct:free"

def get_detailed_market_data(is_morning):
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

def fetch_news_detailed():
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    # 2026年の旬なキーワードに調整
    queries = ["NVIDIA 2026", "US economy Jan 2026", "China US trade 2026"]
    collected = ""
    jst = pytz.timezone('Asia/Tokyo')
    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', page_size=3)
            for art in res.get('articles', []):
                utc_dt = datetime.datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
                date_str = utc_dt.astimezone(jst).strftime('%Y/%m/%d %H:%M')
                collected += f"■DATE: {date_str} (JST)\nTITLE: {art['title']}\nSUMMARY: {art.get('description','')[:200]}\n\n"
        except: pass
    return collected

def call_ai(prompt):
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/my-stock-ai"
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5 # 創造性を下げて、事実に基づいた出力を優先
            },
            timeout=180
        )
        data = res.json()
        return data['choices'][0]['message']['content']
    except Exception:
        return "AI生成エラー。時間を空けて再試行してください。"

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    current_date_str = now.strftime('%Y年%m月%d日')
    
    is_morning = 5 <= now.hour <= 11
    market_info = get_detailed_market_data(is_morning)
    news_info = fetch_news_detailed()

    # パート1：分析編（2026年であることを強調）
    prompt1 = f"""
あなたは米国株シニアアナリストです。今日は【{current_date_str}】です。
絶対に過去（2024年や2025年）の古い情報を話さないでください。提供する2026年1月の最新データのみを使用してください。

【1.ニュース格付け】【2.NVDA・半導体テクニカル分析】【3.政治・AI動向】を4000文字以上の圧倒的分量で執筆せよ。
ニュース日付（2026年1月）に必ず言及し、絵文字多用で情熱的に書くこと。

データ:
{market_info}
最新ニュース(2026年):
{news_info}
"""
    part1 = call_ai(prompt1)
    
    print("Waiting for 60 seconds...")
    time.sleep(60)

    # パート2：予測/答え合わせ編
    mode_text = "【朝の答え合わせ】" if is_morning else "【夕方の今夜予想】"
    prompt2 = f"""
今日は【{current_date_str}】です。プロアナリストとして{mode_text}を執筆せよ。
2026年現在の市場心理、先物動向、テクニカルな心理戦を深く論じること。
過去の古いニュースは一切無視し、現在の値動きのみに集中してください。

最新データ:
{market_info}
"""
    part2 = call_ai(prompt2)

    full_report = f"📊 **US Stock Strategy Report ({current_date_str})**\n\n{part1}\n\n{'='*20}\n\n{part2}"

    if DISCORD_WEBHOOK_URL:
        chunks = [full_report[i:i+1700] for i in range(0, len(full_report), 1700)]
        for chunk in chunks:
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=chunk).execute()
            time.sleep(2)

if __name__ == "__main__":
    main()
