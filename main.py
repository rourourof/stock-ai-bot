import os
import requests
import datetime
import pytz
import yfinance as yf
import time
from newsapi import NewsApiClient

# === 設定 (GitHub Secretsから取得) ===
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 無料モデルの優先順位（GeminiがダメならLlamaが動く冗長化）
FREE_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-7b-instruct:free"
]

def get_detailed_market_data():
    """ yfinanceから2026年現在のリアルタイム株価・先物を取得 """
    targets = {
        "NVDA": "NVIDIA", 
        "^SOX": "PHLX半導体指数", 
        "ES=F": "S&P500先物", 
        "NQ=F": "ナスダック100先物",
        "^TNX": "米10年債利回り"
    }
    report_data = ""
    for ticker, name in targets.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="10d")
            if len(hist) < 2: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            
            # テクニカル分析用データ
            sma5 = hist['Close'].rolling(window=5).mean().iloc[-1]
            diff_sma5 = ((curr['Close'] - sma5) / sma5) * 100
            
            report_data += f"【{name} ({ticker})】\n"
            report_data += f"  - 現在値: {curr['Close']:.2f}\n"
            report_data += f"  - 前日比: {change_pct:+.2f}%\n"
            report_data += f"  - 5日移動平均乖離率: {diff_sma5:+.2f}%\n"
        except: pass
    return report_data

def fetch_latest_news():
    """ 2026年1月の最新ニュースを取得 """
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    # 直近48時間のニュースに限定
    start_date = (now - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    
    collected = ""
    for q in ["NVIDIA AI", "US Stock Market", "Fed Interest Rate"]:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=start_date, page_size=4)
            for art in res.get('articles', []):
                collected += f"■ {art['publishedAt']} | {art['title']}\n  概要: {art.get('description','')[:200]}\n\n"
        except: pass
    return collected

def call_ai_with_retry(prompt):
    """ OpenRouterの無料枠制限を突破するためのリトライ機能 """
    for model_name in FREE_MODELS:
        try:
            print(f"Executing with model: {model_name}...")
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/my-stock-ai"
                },
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.8 # 長文を出すため少し高めに設定
                },
                timeout=180
            )
            data = res.json()
            if 'choices' in data:
                return data['choices'][0]['message']['content'], model_name
            else:
                print(f"Error from {model_name}: {data.get('error')}")
                time.sleep(10)
        except Exception as e:
            print(f"Exception calling {model_name}: {e}")
            continue
    return None, None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    current_jst = now.strftime('%Y年%m月%d日 %H時%M分')
    is_morning = 5 <= now.hour <= 11
    
    market_info = get_detailed_market_data()
    news_info = fetch_latest_news()

    # AIをサボらせず、5000文字級の出力を強制するプロンプト
    prompt = f"""
あなたは世界最高峰の米国株シニアストラテジストです。
【本日の日付: {current_jst}】

【警告】2024年や2025年の情報は「歴史」です。現在は2026年1月であり、提供された最新データのみに基づき執筆してください。
読者が10分間かけて読み込む、圧倒的な熱量と情報量の「投資家向け深掘りレポート」を日本語で作成してください。

【必須構成テンプレート：以下のセクションごとに枠を設け、各項目500文字以上で詳しく執筆せよ】

1. 🚀 **2026年最新ニュース・インパクト・ランキング**
   提供されたニュースを精査し、今夜（または昨夜）の市場を揺るがした要因を1位から3位まで格付けしてください。各ランクで「なぜこれが重要か」「2026年のAIバブルにどう影響するか」を徹底解説してください。

2. 💎 **NVIDIA (NVDA) ＆ 半導体セクター別枠分析**
   NVIDIAの現在価格やSOX指数の動きを分析し、テクニカル的な視点（支持線・抵抗線）とファンダメンタルズ（次世代チップ需要）の両面から詳述してください。「割愛」は一切禁止です。

3. 🏗️ **地政学・AI規制・対中政策のトライアングル**
   米中関係、AI規制法案、金利動向が、ハイテク株のPERにどう影響しているか、プロの鋭い洞察を記述してください。

4. 🔥 **【最重要】{'夜明けの全貌：答え合わせと要因特定' if is_morning else '今夜の運命：先物から読む3つの爆発シナリオ'}**
   {'昨夜の市場でどの銘柄が「騙し上げ」だったか、どの材料が無視されたかを峻別せよ。' if is_morning else '現在の先物価格に基づき、メイン・強気・弱気の3つの具体的価格帯予測を提示せよ。'}

5. 📰 **2026/01 最新ヘッドライン・データ集**
   提供されたデータの要約。

【執筆の掟】
- 絵文字を多用し、フォントの太字（**）を使って重要箇所を強調せよ。
- 「詳細不明」という言葉は絶対に使わず、プロとして断定的な推論を行え。
- スマホで何回もスクロールしなければ読みきれないほどの分量を目指せ。

データ:
{market_info}
最新ニュース:
{news_info}
"""

    report, used_model = call_ai_with_retry(prompt)

    if report and DISCORD_WEBHOOK_URL:
        # モデル名を末尾に付与
        full_text = report + f"\n\n*(Analysis Model: {used_model} | Reported at {current_jst} JST)*"
        
        # Discordの2000文字制限に合わせて分割送信
        chunks = [full_text[i:i+1900] for i in range(0, len(full_text), 1900)]
        for i, chunk in enumerate(chunks):
            # 最初のチャンクにタイトルを付与
            prefix = f"📊 **US Stock Strategy Report - Part {i+1}**\n" if i == 0 else ""
            requests.post(DISCORD_WEBHOOK_URL, json={"content": prefix + chunk})
            time.sleep(2) # Discordのレート制限対策
    else:
        print("Failed to generate report with all available models.")

if __name__ == "__main__":
    main()
