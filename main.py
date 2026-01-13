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
            hist = t.history(period="10d")
            if len(hist) < 5: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            sma5 = hist['Close'].rolling(window=5).mean().iloc[-1]
            report_data += f"\n【{name} ({ticker})】\n- 価格: {curr['Close']:.2f} ({change_pct:+.2f}%)\n- 5日線乖離: {((curr['Close']-sma5)/sma5)*100:+.2f}%\n"
        except: pass
    return report_data

def fetch_news_detailed():
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    # 2024年の混入を防ぐため、物理的に「直近2日以内」の記事に限定
    start_date = (datetime.datetime.now(jst) - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    queries = ["NVIDIA AI", "US Stock Market", "Semiconductor"]
    collected = ""
    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=start_date, page_size=4)
            for art in res.get('articles', []):
                collected += f"■{art['title']}\n{art.get('description','')[:200]}\n"
        except: pass
    return collected

def call_gemini(prompt):
    """Gemini 2.0 Flash専用のリトライ機能付き呼び出し"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/my-stock-ai"
    }
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8
    }

    for attempt in range(3): # 最大3回リトライ
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=180)
            data = res.json()
            if 'choices' in data:
                return data['choices'][0]['message']['content']
            
            # エラーメッセージ（Rate Limit等）が出た場合は少し待機してリトライ
            print(f"Attempt {attempt+1} failed: {data.get('error', 'Unknown Error')}")
            time.sleep(30 * (attempt + 1)) 
        except Exception as e:
            print(f"Connection error: {e}")
            time.sleep(30)
    return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    current_date = now.strftime('%Y/%m/%d')
    is_morning = 5 <= now.hour <= 11
    
    market_info = get_detailed_market_data(is_morning)
    news_info = fetch_news_detailed()

    # モード判定と指示（あなたの理想ロジックを継承）
    mode = "朝：【答え合わせ】" if is_morning else "夕：【シナリオ予想】"
    instruction = "昨夜の的中判定と要因分析" if is_morning else "今夜のメイン・強気・弱気の3段階予想"

    prompt = f"""
現在は【{current_date}】です。過去の情報は捨て、最新データのみで執筆せよ。
あなたは米国株のシニアストラテジストとして、5000文字級の情熱的なレポートを作成してください。

【配信モード】: {mode}
【市場データ】: {market_info}
【ニュースソース】: {news_info}

【必須構成】:
1. **影響度ランキング**（ニュース格付け）
2. **NVIDIA & 半導体別枠分析**（テクニカル・攻防予測）
3. **政治・地政学・AI・対中政策**
4. **{instruction}**

ルール：絵文字多用。読むのに10分かかる圧倒的分量。詳細不明は厳禁。
"""

    report = call_gemini(prompt)

    if report and DISCORD_WEBHOOK_URL:
        # 1800文字ずつ分割送信
        chunks = [report[i:i+1800] for i in range(0, len(report), 1800)]
        for i, chunk in enumerate(chunks):
            header = f"📊 **Market Report Part {i+1}**\n" if i == 0 else ""
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=header + chunk).execute()
            time.sleep(2)

if __name__ == "__main__":
    main()
