import os
import requests
import datetime
import pytz
import yfinance as yf
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
            if len(hist) < 2: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            sma5 = hist['Close'].rolling(window=5).mean().iloc[-1]
            report_data += f"\n【{name} ({ticker})】\n- 価格: {curr['Close']:.2f} ({change_pct:+.2f}%)\n- 5日線乖離: {((curr['Close']-sma5)/sma5)*100:+.2f}%\n"
        except: pass
    return report_data

def fetch_news_detailed():
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    queries = ["NVIDIA AI", "US Stock Market FED", "US China Politics"]
    collected = ""
    jst = pytz.timezone('Asia/Tokyo')
    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', page_size=4)
            for art in res.get('articles', []):
                utc_dt = datetime.datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
                date_str = utc_dt.astimezone(jst).strftime('%m/%d %H:%M')
                collected += f"■DATE: {date_str}\nTITLE: {art['title']}\nDETAIL: {art.get('description','')[:300]}\n\n"
        except: pass
    return collected

def call_ai(prompt):
    """OpenRouter呼び出しの共通関数"""
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8
            },
            timeout=120
        )
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"AI生成エラー詳細: {str(e)}"

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    hour = now.hour
    is_morning = 5 <= hour <= 11
    market_info = get_detailed_market_data(is_morning)
    news_info = fetch_news_detailed()

    # --- 第1パート：市場分析とニュース深掘り ---
    prompt1 = f"""
    米国株シニアアナリストとして、以下のデータから【ニュース分析・影響度格付け・テクニカル分析】のセクションを、2000文字以上の圧倒的分量で執筆してください。
    【現在時刻】: {now.strftime('%Y/%m/%d %H:%M')}
    【市場データ】: {market_info}
    【ニュース】: {news_info}
    条件：絵文字多用、ニュースの日付に言及し『織り込み度』を解説、NVIDIA/半導体は別枠で詳細に。
    """
    part1 = call_ai(prompt1)

    # --- 第2パート：答え合わせ または シナリオ予想 ---
    mode_text = "【朝の答え合わせ】" if is_morning else "【夕方のシナリオ予想】"
    prompt2 = f"""
    米国株シニアアナリストとして、以下の状況を踏まえ、{mode_text}セクションを2000文字以上の圧倒的分量で執筆してください。
    【市場データ】: {market_info}
    指示：{'昨夜の的中判定と無視されたニュースの特定' if is_morning else '先物と材料から読む今夜の3シナリオ予測'}を情熱的に書いてください。
    """
    part2 = call_ai(prompt2)

    full_report = f"{part1}\n\n{'='*30}\n\n{part2}"

    if DISCORD_WEBHOOK_URL:
        # 1800文字ずつ分割送信
        chunks = [full_report[i:i+1800] for i in range(0, len(full_report), 1800)]
        for i, chunk in enumerate(chunks):
            header = f"📊 **Market Report (Part {i+1}/{len(chunks)})**\n" if i == 0 else ""
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=header + chunk).execute()

if __name__ == "__main__":
    main()
