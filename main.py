import os, requests, datetime, pytz, time
import yfinance as yf
from discord_webhook import DiscordWebhook

# === 環境変数 ===
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_analysis():
    # 計算ロジック（そのまま）
    tickers = {"NVDA": "NVIDIA", "^SOX": "半導体(SOX)", "^IXIC": "NASDAQ"}
    results = {}
    for sym, name in tickers.items():
        try:
            df = yf.Ticker(sym).history(period="40d")
            curr, prev = df.iloc[-1], df.iloc[-2]
            results[sym] = {
                "name": name, "close": round(curr['Close'], 2),
                "change_pct": round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2),
                "range_judgment": "上抜け" if curr['Close'] > prev['High'] else ("下抜け" if curr['Close'] < prev['Low'] else "レンジ内")
            }
        except: pass
    return results

def call_openrouter_xiaomi(prompt):
    # 現在、空いていて狙い目の無料モデル：Xiaomi MIMO-V2-Flash
    model_name = "xiaomi/mimo-v2-flash:free"
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "あなたは精密な分析を行う金融ストラテジストです。簡潔かつ論理的な日本語で、データの背景にある市場心理を要約してください。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }

    # 429(枠不足)対策：最大3回リトライ、待機時間を1分以上に設定
    for i in range(3):
        try:
            print(f"Connecting to Xiaomi Model (Attempt {i+1})...")
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content']
            elif res.status_code == 429:
                print("Quota limit hit. Waiting 65 seconds for the next slot...")
                time.sleep(65) # 無料枠の解除を待つために1分強待機
            else:
                print(f"Error {res.status_code}: {res.text}")
                time.sleep(5)
        except Exception as e:
            print(f"Exception: {e}")
            time.sleep(5)
            
    return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    
    # 土日は休止（米国市場に合わせる場合）
    if now.weekday() >= 5: 
        print("Weekend - Market closed.")
        return

    m_data = get_market_analysis()
    time_tag = "06:07" if 5 <= now.hour <= 11 else "18:07"
    
    # 推論とまとめの質を上げるためのプロンプト
    prompt = f"""
以下の市場データを元に、プロの投資家向けレポートを執筆してください。
【データ】{m_data}

【構成案】
1. NVIDIA(NVDA)と半導体指数(SOX)の現状分析：両者の乖離や連動性について。
2. テクニカル判断：レンジ状況から見る「強気・弱気」の分岐点。
3. 今後の展望：次の一手として注目すべき要素。
4. 免責事項：投資助言ではない旨。

文章は箇条書きを適度に使用し、読みやすく深みのある表現を心がけてください。
"""

    report = call_openrouter_xiaomi(prompt)
    
    # 最終的な失敗時の予備出力
    if not report:
        report = "【数値速報】AIが混雑しているため、生データのみ配信します。\n\n"
        for k
