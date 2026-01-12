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

# 無料で最も安定しているLlama 3.3を指定
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
    # 検索を絞ってトークン（文字数）を節約
    queries = ["NVIDIA AI", "US Market"]
    collected = ""
    jst = pytz.timezone('Asia/Tokyo')
    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=2)
            for art in res.get('articles', []):
                utc_dt = datetime.datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
                date_str = utc_dt.astimezone(jst).strftime('%m/%d %H:%M')
                collected += f"■{date_str} {art['title']}\n{art.get('description','')[:150]}\n\n"
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
                "temperature": 0.7
            },
            timeout=180
        )
        data = res.json()
        if 'choices' in data:
            return data['choices'][0]['message']['content']
        else:
            return f"AIエラー: {data.get('error', {}).get('message', '制限エラー')}"
    except Exception as e:
        return f"通信エラー: {str(e)}"

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    is_morning = 5 <= now.hour <= 11
    market_info = get_detailed_market_data(is_morning)
    news_info = fetch_news_detailed()

    # パート1：分析編
    prompt1 = f"米国株プロアナリストとして【ニュース格付け】【NVDA・半導体テクニカル分析】【政治・AI動向】を長文で執筆せよ。絵文字多用、ニュースの日付に言及すること。\nデータ:{market_info}\nニュース:{news_info}"
    part1 = call_ai(prompt1)
    
    # 制限回避のため、長めの60秒待機
    print("Waiting for 60 seconds to avoid rate limits...")
    time.sleep(60)

    # パート2：予測/答え合わせ編
    mode_text = "【朝の答え合わせ】予測的中判定" if is_morning else "【夕方の今夜予想】3つの詳細シナリオ"
    prompt2 = f"プロのアナリストとして{mode_text}を長文で執筆せよ。無視されたニュースや先物動向、テクニカルな心理戦を深く論じること。\nデータ:{market_info}"
    part2 = call_ai(prompt2)

    full_report = f"📊 **US Stock Strategy Report**\n{part1}\n\n{'='*20}\n\n{part2}"

    if DISCORD_WEBHOOK_URL:
        chunks = [full_report[i:i+1700] for i in range(0, len(full_report), 1700)]
        for chunk in chunks:
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=chunk).execute()
            time.sleep(2)

if __name__ == "__main__":
    main()
