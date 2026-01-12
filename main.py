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

def get_detailed_market_data(is_morning):
    """株価・先物・テクニカル指標の取得"""
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
            
            report_data += f"\n【{name} ({ticker})】\n"
            report_data += f"- 現在値/終値: {curr['Close']:.2f} ({change_pct:+.2f}%)\n"
            report_data += f"- 出来高: {curr['Volume']:,}\n"
            report_data += f"- 5日移動平均乖離: {((curr['Close']-sma5)/sma5)*100:+.2f}%\n"
            if is_morning:
                report_data += f"- 日中安値からの戻り: {((curr['Close']-curr['Low'])/curr['Low'])*100:+.2f}%\n"
        except: pass
    return report_data

def fetch_news_detailed():
    """ニュースを詳細に取得（日付付き）"""
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    queries = ["NVIDIA AI", "US Stock Market FED", "US China Politics", "Semiconductor Market"]
    collected = ""
    jst = pytz.timezone('Asia/Tokyo')

    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', page_size=5)
            for art in res.get('articles', []):
                # ISO形式の日時を日本時間に変換
                utc_dt = datetime.datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
                jst_dt = utc_dt.astimezone(jst)
                date_str = jst_dt.strftime('%m/%d %H:%M')

                content = art.get('description') or art.get('content') or ""
                collected += f"■DATE: {date_str} (JST)\nSOURCE: {art['source']['name']}\nTITLE: {art['title']}\nDETAIL: {content[:400]}\n\n"
        except: pass
    return collected

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    day = now.strftime('%A')
    hour = now.hour
    
    is_morning = 5 <= hour <= 11
    market_info = get_detailed_market_data(is_morning)
    news_info = fetch_news_detailed()

    if day == "Sunday":
        mode = "日曜版：【今週の総括】全ニュースと値動きの徹底解剖"
        time_instruction = "1週間の全材料を振り返り、来週の戦略を4000文字以上の圧倒的ボリュームで解説してください。"
    elif is_morning:
        mode = "平日朝：【前夜の答え合わせ】予想の的中検証と要因分析"
        time_instruction = f"本日は{now.strftime('%m月%d日')}。昨夜の予測と実際の終値を比較し、どのニュースがどう影響したか、的中判定を行ってください。"
    else:
        mode = "平日夕：【今夜のシナリオ予想】先物とテクニカルから読む展望"
        time_instruction = "現在の先物と最新ニュースに基づき、今夜のメイン・強気・弱気の3シナリオを提示してください。"

    prompt = f"""
あなたはプロの米国株シニアストラテジストとして、10分かけて読むに値する長大かつ詳細なレポートを日本語で作成してください。

【本日の配信モード】: {mode}
【現在時刻】: {now.strftime('%Y/%m/%d %H:%M')} (JST)
【市場データ】: {market_info}
【詳細ニュースソース】: {news_info}

【必須構成】:
1. **影響度ランキング**：ニュースを市場への影響度順（NVDA/半導体/金利/政治等）に格付け。※各ニュースの日付を考慮し、鮮度の高いものを優先すること。
2. **NVIDIA & 半導体別枠分析**：先物、出来高、テクニカルを用いた今夜の攻防予測。
3. **政治・地政学・AI・対中政策**：最新の政治発言がセクターに与える影響。
4. **実際の詳細ニュース一覧**：日付、ソースを明記して整理。
5. **答え合わせ or 予測（重要）**:
   {time_instruction}

【執筆ルール】:
- 「割愛」「詳細不明」は厳禁。
- 読むのに10分かかる分量（約4000〜5000文字）を死守すること。
- 各ニュースが何時間前のものかに言及し、市場の『織り込み度』を論理的に解説してください。
"""

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

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=120)
        res_json = res.json()
        report = res_json['choices'][0]['message']['content']
    except Exception as e:
        report = f"⚠️ AI生成エラーが発生しました: {str(e)}"

    if DISCORD_WEBHOOK_URL:
        chunks = [report[i:i+1800] for i in range(0, len(report), 1800)]
        for i, chunk in enumerate(chunks):
            header = f"📊 **{mode} (Part {i+1}/{len(chunks)})**\n" if i == 0 else ""
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=header + chunk).execute()

if __name__ == "__main__":
    main()
