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
    queries = ["NVIDIA AI", "US Stock Market", "US Politics"]
    collected = ""
    jst = pytz.timezone('Asia/Tokyo')
    for q in queries:
        try:
            # ニュース件数を少し減らして安定性を向上
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', page_size=2)
            for art in res.get('articles', []):
                utc_dt = datetime.datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
                date_str = utc_dt.astimezone(jst).strftime('%m/%d %H:%M')
                collected += f"■{date_str} {art['title']}\n{art.get('description','')[:200]}\n\n"
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
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8
            },
            timeout=180
        )
        data = res.json()
        if 'choices' in data:
            return data['choices'][0]['message']['content']
        else:
            # エラーメッセージを具体的に出す
            return f"AIエラー: {data.get('error', {}).get('message', '不明な制限')}"
    except Exception as e:
        return f"通信エラー: {str(e)}"

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    is_morning = 5 <= now.hour <= 11
    market_info = get_detailed_market_data(is_morning)
    news_info = fetch_news_detailed()

    # パート1：ニュース・テクニカル分析
    prompt1 = f"米国株アナリストとして、以下のデータから【1.ニュース格付け】【2.NVDA・半導体分析】【3.政治・AI動向】を2000文字以上の超長文で執筆せよ。ニュース日付に言及し、絵文字多用で情熱的に書くこと。\nデータ:{market_info}\nニュース:{news_info}"
    part1 = call_ai(prompt1)
    
    # 無料枠のRate Limit（連投制限）を避けるために30秒待機
    time.sleep(30)

    # パート2：答え合わせ/予測
    mode_text = "【朝の答え合わせ】的中判定と織り込み済みニュース分析" if is_morning else "【夕方のシナリオ予測】先物から読む3つの展望"
    prompt2 = f"米国株アナリストとして、以下に基づき{mode_text}を2000文字以上の長文で執筆せよ。無視されたニュースやテクニカルな攻防を深く鋭く論じること。\nデータ:{market_info}"
    part2 = call_ai(prompt2)

    full_report = f"📊 **Professional Report**\n{part1}\n\n{'='*20}\n\n{part2}"

    if DISCORD_WEBHOOK_URL:
        # 1700文字ずつに分割（Discordの制限に余裕を持たせる）
        chunks = [full_report[i:i+1700] for i in range(0, len(full_report), 1700)]
        for chunk in chunks:
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=chunk).execute()
            time.sleep(1) # Discord側のレート制限対策

if __name__ == "__main__":
    main()
