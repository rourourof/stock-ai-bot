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
    tickers = {"NVDA": "NVIDIA", "^SOX": "PHLX Semiconductor Index"}
    report_data = ""
    for ticker, name in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if len(hist) < 2: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            vol_ratio = (curr['Volume'] / hist['Volume'].mean()) * 100
            report_data += f"\n【{name} ({ticker})】\n- 現在値: ${curr['Close']:.2f} (前日比: {change_pct:+.2f}%)\n- 出来高比: {vol_ratio:.1f}%\n"
        except: pass
    return report_data

def fetch_news():
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    topics = ["US Stock Market", "NVIDIA AI", "US Politics China"]
    collected = ""
    for query in topics:
        try:
            res = newsapi.get_everything(q=query, language='en', sort_by='relevancy', page_size=3)
            for art in res.get('articles', []):
                collected += f"・{art['title']}\n"
        except: pass
    return collected

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    day = now.strftime('%A')
    hour = now.hour

    market_info = get_detailed_market_data()
    news_info = fetch_news()

    if day == "Sunday":
        mode = "日曜版：【今週の総括】全ニュースと値動きの徹底解剖"
    elif 5 <= hour <= 10:
        mode = "平日朝：【答え合わせと分析】昨夜の予想検証と織り込み度チェック"
    else:
        mode = "平日夕：【今夜のシナリオ予想】材料から読む期待値とトレンド"

    # プロンプトを少し整理してAIが「書きやすい」ように調整
    prompt = f"""
あなたは米国株のプロアナリストです。以下のデータから、読むのに10分かかる非常に濃密なレポート（約4000文字）を執筆してください。

【本日のモード】: {mode}
【市場データ】: {market_info}
【主要ニュース】: {news_info}

【構成ルール】
1. 影響度ランキング（NVDA/半導体/金利/政治等）
2. NVIDIA & 半導体セクター別枠分析（テクニカル視点）
3. 政治・対中・AI動向の別枠解説
4. 実際のニュース一覧
5. 朝なら「答え合わせ」、夕なら「今夜の予測」
6. 織り込み済み/無視されたニュースの分析

条件：絵文字を多用し、非常に長い文章で、具体的かつ断定的な予測を行ってください。
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/my-stock-ai",
        "X-Title": "Stock Analysis Bot"
    }
    
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7 # 創造性を少し上げて長文を出しやすくする
    }

    try:
        # timeoutを120秒に設定
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", 
                                 headers=headers, json=payload, timeout=120)
        res_json = response.json()
        
        if "choices" in res_json:
            report = res_json['choices'][0]['message']['content']
        else:
            # エラーの詳細をDiscordに送るようにする
            err_info = res_json.get('error', {}).get('message', '不明なエラー')
            report = f"⚠️ AI生成エラーが発生しました。\n詳細: {err_info}\n(無料枠の制限または長文生成によるタイムアウトの可能性があります。)"

    except requests.exceptions.Timeout:
        report = "⚠️ タイムアウトエラー: AIの回答が長すぎて制限時間を超えました。"
    except Exception as e:
        report = f"⚠️ システムエラー: {str(e)}"

    if DISCORD_WEBHOOK_URL:
        # 分割送信
        chunks = [report[i:i+1900] for i in range(0, len(report), 1900)]
        for i, chunk in enumerate(chunks):
            prefix = f"【{mode} - Part {i+1}/{len(chunks)}】\n" if i == 0 else ""
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=prefix + chunk).execute()

if __name__ == "__main__":
    main()
