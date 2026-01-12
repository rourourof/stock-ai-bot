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
            if len(hist) < 2: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            report_data += f"\n【{name} ({ticker})】価格: {curr['Close']:.2f} ({change_pct:+.2f}%)\n"
        except: pass
    return report_data

def fetch_news_detailed():
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    # 古いニュースを避けるため、3日前からの記事のみ取得
    three_days_ago = (now - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
    
    queries = ["NVIDIA AI", "US Stock Market Fed", "US Politics China"]
    collected = ""
    for q in queries:
        try:
            # from_paramで日付を2026年1月に固定
            res = newsapi.get_everything(q=q, language='en', sort_by='relevancy', from_param=three_days_ago, page_size=4)
            for art in res.get('articles', []):
                utc_dt = datetime.datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
                date_str = utc_dt.astimezone(jst).strftime('%Y/%m/%d %H:%M')
                collected += f"■DATE: {date_str} (JST)\nTITLE: {art['title']}\nDETAIL: {art.get('description','')[:300]}\n\n"
        except: pass
    return collected

def call_ai(prompt):
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/my-stock-ai"},
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=180
        )
        data = res.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"エラー: {str(e)}"

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    current_jst = now.strftime('%Y/%m/%d %H:%M')
    is_morning = 5 <= now.hour <= 11
    
    market_info = get_detailed_market_data(is_morning)
    news_info = fetch_news_detailed()

    # 条件を1つずつ「枠」として指示する超詳細プロンプト
    prompt = f"""
あなたはプロの米国株アナリストです。現在は【{current_jst} (JST)】です。
提供された2026年1月の最新データのみを使用し、読むのに10分かかる圧倒的ボリューム（5000文字以上）でレポートしてください。

【厳守条件：以下の別枠を必ず設けて解説すること】
1. **重要ニュース影響度ランキング**：影響が高い順（NVDA/半導体/金利/政治等）に格付けし、各項目を詳細に。
2. **NVIDIA別枠分析**：前日比、値動き、出来高の振り返り。
3. **半導体関連別枠分析**：NVIDIA以外のセクター動向。
4. **米国政治・AI・対中政策別枠**：政治家の発言、地政学リスク、AI規制。
5. **最新ニュース詳細一覧**：日付（2026/01）を明記し内容を詳述。
6. **{'朝の答え合わせ' if is_morning else '今夜のシナリオ予想'}**：
   - {'昨夜の予測と実際の値動きの的中判定。無視されたニュースと織り込み済みニュースの特定' if is_morning else '先物データを用いた今夜のメイン・強気・弱気の3段階予想'}

【ルール】
- 「詳細不明」「割愛」は禁止。
- 絵文字を多用し、投資家を鼓舞する情熱的な文体で。
- 歴史的な話ではなく、今日、今夜、明日の話をすること。

データ:
{market_info}
最新ニュースソース:
{news_info}
"""

    # 1回で書き切らせるためにGeminiの性能を信じます（分割すると文脈が切れるため）
    report = call_ai(prompt)

    if DISCORD_WEBHOOK_URL:
        # 1800文字ずつ分割送信
        chunks = [report[i:i+1800] for i in range(0, len(report), 1800)]
        for i, chunk in enumerate(chunks):
            header = f"🚀 **{now.strftime('%m/%d')} US Stock Report (Part {i+1}/{len(chunks)})**\n" if i == 0 else ""
            requests.post(DISCORD_WEBHOOK_URL, json={"content": header + chunk})
            time.sleep(1)

if __name__ == "__main__":
    main()
