import os
import requests
import datetime
import pytz
import yfinance as yf
import pandas as pd
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === 設定 ===
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_detailed_market_data():
    """NVDAと半導体指数のテクニカルデータを取得"""
    tickers = {"NVDA": "NVIDIA", "^SOX": "PHLX Semiconductor Index"}
    report_data = ""
    for ticker, name in tickers.items():
        try:
            t = yf.Ticker(ticker)
            # 直近5日間のデータを取得してテクニカル計算
            hist = t.history(period="5d")
            if len(hist) < 2: continue
            
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            vol_ratio = (curr['Volume'] / hist['Volume'].mean()) * 100
            
            report_data += f"\n【{name} ({ticker})】\n"
            report_data += f"- 現在値: ${curr['Close']:.2f} (前日比: {change_pct:+.2f}%)\n"
            report_data += f"- 出来高: {curr['Volume']:,} (平均比: {vol_ratio:.1f}%)\n"
            report_data += f"- 高値/安値: ${curr['High']:.2f} / ${curr['Low']:.2f}\n"
            # テクニカル視点 (簡易RSI)
            report_data += f"- 直近トレンド: {'強気' if curr['Close'] > hist['Close'].mean() else '調整気味'}\n"
        except:
            report_data += f"\n{name}のデータ取得失敗\n"
    return report_data

def fetch_news():
    """多角的なニュース収集"""
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    topics = {
        "Market": "US Stock Market",
        "Politics": "US Politics Biden Trump China policy",
        "AI/Tech": "NVIDIA AI Semiconductor",
        "Economic": "FED Interest rates Inflation"
    }
    collected = ""
    for category, query in topics.items():
        try:
            res = newsapi.get_everything(q=query, language='en', sort_by='relevancy', page_size=4)
            for art in res.get('articles', []):
                collected += f"[{category}] {art['title']} - {art.get('description', '')[:100]}...\n"
        except: pass
    return collected

def main():
    # 日本時間 (JST) 判定
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    day = now.strftime('%A')
    hour = now.hour

    # 1. データ収集
    market_info = get_detailed_market_data()
    news_info = fetch_news()

    # 2. 配信モードの決定
    if day == "Sunday":
        mode = "日曜版：【今週の総括】全ニュースと値動きの徹底解剖"
        specific_instruction = "今週1週間のトレンドを振り返り、来週に向けた長期的な展望を4000文字以上で論じてください。"
    elif 5 <= hour <= 10:
        mode = "平日朝：【答え合わせと分析】昨夜の予想検証と織り込み度チェック"
        specific_instruction = "昨夜の市場でどのニュースが『織り込み済み』で、どのニュースが『サプライズ』だったかを峻別してください。"
    else:
        mode = "平日夕：【今夜のシナリオ予想】材料から読む期待値とトレンド"
        specific_instruction = "今夜の米市場開場に向けて、メイン・強気・弱気の3シナリオを具体的な理由と共に提示してください。"

    # 3. AIプロンプト（条件をすべて凝縮）
    prompt = f"""
あなたは米国株専門のシニアストラテジストとして、投資家が10分かけて読むに値する、非常に濃密で情熱的なレポートを作成してください。

【本日のモード】: {mode}

【入力データ】:
市場数値: {market_info}
最新ヘッドライン: {news_info}

【必須構成（以下の順序で別枠を設けること）】:
1. **影響度ランキング**：収集したニュースを、株式市場への影響度が高い順（NVDA/半導体/金利/政治等）に格付けし、論理的な理由を添える。
2. **NVIDIA & 半導体別枠分析**：NVDAとSOX指数の前日比、出来高、値動きをテクニカル視点（レジスタンス、支持線等）で振り返る。
3. **政治・地政学・AI別枠**：政治家の発言、対中政策、AI規制の動向。
4. **最新ニュース一覧**：実際のヘッドラインまとめ。
5. **答え合わせ or 予測（重要）**:
   - 朝：前夜の予想の的中判定と「聞かなかったニュース（無視された材料）」の分析。
   - 夕：今夜のトレンド、注目経済指標を踏まえた具体的な値動き予想。
6. **投資シナリオ**：必ず理由を付随させ、論理的な結論を出すこと。

【スタイル】:
- 文字数：4000文字以上を目指す長文。
- 絵文字を多用し、エンターテインメント性とプロの分析を両立させる。
- 曖昧な表現を避け、プロフェッショナルな断定と予測を行う。
"""

    # 4. OpenRouter呼び出し
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
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        report = res.json()['choices'][0]['message']['content']
    except Exception as e:
        report = f"AI生成エラー: {str(e)}"

    # 5. Discord送信 (2000文字制限対応の分割送信)
    if DISCORD_WEBHOOK_URL:
        # ヘッダーを付けて分割
        chunks = [report[i:i+1900] for i in range(0, len(report), 1900)]
        for i, chunk in enumerate(chunks):
            prefix = f"【{mode} - Part {i+1}/{len(chunks)}】\n" if i == 0 else ""
            webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=prefix + chunk)
            webhook.execute()

if __name__ == "__main__":
    main()
