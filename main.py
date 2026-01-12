import os
import requests
import datetime
import pytz
import yfinance as yf
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# 設定
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_data():
    """NVIDIAと半導体(SOXL等)のデータを取得"""
    tickers = {"NVDA": "NVIDIA", "^SOX": "PHLX Semiconductor"}
    data_str = ""
    for ticker, name in tickers.items():
        t = yf.Ticker(ticker)
        hist = t.history(period="2d")
        if len(hist) >= 2:
            prev = hist['Close'].iloc[-2]
            curr = hist['Close'].iloc[-1]
            diff = ((curr - prev) / prev) * 100
            vol = hist['Volume'].iloc[-1]
            data_str += f"- {name}({ticker}): 終値 {curr:.2f} ({diff:+.2f}%) / 出来高: {vol}\n"
    return data_str

def main():
    # 日本時間の現在時刻を取得
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    day_of_week = now.strftime('%A') # Monday, Sunday...
    hour = now.hour

    # 1. ニュース取得（広範囲に検索）
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    q_list = ["US Stock Market", "NVIDIA", "Semiconductor", "US Politics", "China policy AI"]
    raw_news = ""
    for q in q_list:
        res = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=5)
        for art in res.get('articles', []):
            raw_news += f"[{q}] {art['title']}: {art.get('description', '')}\n"

    # 2. 市場データの取得
    market_stats = get_market_data()

    # 3. 配信タイミングによるモード判定
    if day_of_week == "Sunday":
        mode = "【日曜版：今週の振り返り総集編】1週間の全ニュースと値動きを徹底解剖"
    elif 5 <= hour <= 9:
        mode = "【平日朝：前夜の答え合わせと分析】予想の的中検証と重要ニュースの織り込み度"
    else:
        mode = "【平日夕：今夜のシナリオ予想】トレンドと材料から読む期待値"

    # 4. AIへの超詳細プロンプト
    prompt = f"""
あなたはプロの米国株シニアアナリストです。以下の情報を元に、読むのに10分かかる長文（約4000文字以上）の投資レポートを作成してください。

モード：{mode}
市場データ：{market_stats}
最新ニュース：{raw_news}

【構成案・必須項目】
1. **影響度ランキング**：ニュースを市場への影響度が高い順（NVDA/半導体/金利/政治等）に格付けし、理由を添える。
2. **NVIDIA単独分析**：前日比、値動き、出来高のテクニカル分析。
3. **半導体セクター分析**：NVIDIA以外の半導体全体の動向。
4. **米国政治・対中・AIセクション**：政治家の発言、対中政策、AI規制等の深掘り。
5. **最新ニュース一覧**：実際のヘッドラインを整理。
6. **答え合わせと予測**：
   - 朝なら：前夜の予想の的中判定、織り込み済みだったニュース、無視されたニュースの特定。
   - 夕方なら：今夜の具体的な値動きシナリオ（強気・弱気・横ばい）とその理由。
7. **コラム**：株式市場の裏側や、10分間飽きさせない楽しいトーンでの解説。

条件：絵文字を多用し、情熱的かつ冷静な分析を行うこと。分量は非常に長く、専門的であること。
"""

    # 5. OpenRouter呼び出し
    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://github.com/my-stock-ai"
        },
        json={
            "model": "google/gemini-2.0-flash-exp:free",
            "messages": [{"role": "user", "content": prompt}]
        }
    )
    
    report = res.json()['choices'][0]['message']['content']

    # 6. Discord送信（長文なので分割して送信）
    if DISCORD_WEBHOOK_URL:
        # 2000文字制限対策
        for i in range(0, len(report), 1900):
            webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report[i:i+1900])
            webhook.execute()

if __name__ == "__main__":
    main()
