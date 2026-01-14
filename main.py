import os, requests, datetime, pytz, time
import yfinance as yf
from discord_webhook import DiscordWebhook

# === 環境変数 ===
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_analysis():
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

def call_gemini_stable(prompt):
    # 2.0-flash を直接URLに埋め込む、最もエラーが出にくい形式
    # 2026年時点での最新安定エンドポイント
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GOOGLE_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 3000},
        "safetySettings": [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }

    # 429エラー(枠不足)に備えて3回リトライ
    for i in range(3):
        try:
            response = requests.post(url, json=payload, timeout=60)
            data = response.json()
            
            if response.status_code == 200:
                return data['candidates'][0]['content']['parts'][0]['text']
            
            # 429(Quota)なら60秒待機
            if response.status_code == 429:
                print(f"Attempt {i+1}: Quota exceeded. Waiting 60s...")
                time.sleep(60)
                continue
            
            # 404などその他のエラー
            print(f"API Error {response.status_code}: {data.get('error', {}).get('message')}")
            break
        except Exception as e:
            print(f"Exception: {e}")
            time.sleep(10)
    return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    m_data = get_market_analysis()
    
    time_tag = "06:07" if 5 <= now.hour <= 11 else "18:07"
    
    prompt = f"""
プロのストラテジストとして執筆せよ。
データ：{m_data}
条件：NVDAとSOXを対等に分析し、重厚な日本語レビューを出力。
投資助言ではない旨を末尾に記載。
"""

    report = call_gemini_stable(prompt)
    
    if not report:
        report = "【市場概況】AI制限のため数値のみ配信します。\n\n" + str(m_data)

    final_output = f"━━━━━━━━━━━━━━━━━━\n【米国株 市場レビュー】{time_tag} JST\n━━━━━━━━━━━━━━━━━━\n\n{report}\n\n配信時刻：{now.strftime('%Y-%m-%d %H:%M')} JST"
    
    if DISCORD_WEBHOOK_URL:
        # 分割送信
        for i in range(0, len(final_output), 1900):
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final_output[i:i+1900]).execute()
            time.sleep(1)

if __name__ == "__main__":
    main()
