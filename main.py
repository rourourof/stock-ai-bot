import os, requests, datetime, pytz, time
import yfinance as yf
from discord_webhook import DiscordWebhook

# === 環境変数 ===
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_analysis():
    # 簡略化していますが、以前のテクニカル判定ロジックをここに維持してください
    tickers = {"NVDA": "NVIDIA", "^SOX": "半導体指数(SOX)"}
    results = {}
    for sym, name in tickers.items():
        try:
            df = yf.Ticker(sym).history(period="20d")
            curr, prev = df.iloc[-1], df.iloc[-2]
            results[sym] = {
                "name": name, "close": round(curr['Close'], 2),
                "change_pct": round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2)
            }
        except: pass
    return results

def call_gemini_with_retry(prompt):
    # 試行するモデルの優先順位リスト
    # 環境によって 'models/' の有無で挙動が変わるため、直接指定します
    model_candidates = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash-exp" # 2026年時点の最新候補
    ]
    
    for model in model_candidates:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2500},
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        
        try:
            print(f"Trying model: {model}...")
            response = requests.post(url, json=payload, timeout=30)
            data = response.json()
            
            if response.status_code == 200 and 'candidates' in data:
                print(f"Success with {model}!")
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"Model {model} failed: {data.get('error', {}).get('message', 'Unknown error')}")
        except Exception as e:
            print(f"Error connecting to {model}: {e}")
            
    return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    m_data = get_market_analysis()
    
    prompt = f"機関投資家として以下の市場データを分析し、NVDAとSOXを同一比重でレビューせよ。データ: {m_data}"
    
    report = call_gemini_with_retry(prompt)
    
    # 最終的なフォールバック（全モデル失敗時）
    if not report:
        report = "【数値概況】AI接続エラーのため数値のみ配信します。\n" + str(m_data)

    final_output = f"━━━━━━━━━━━━━━━━━━\n【米国株 市場レビュー】\n━━━━━━━━━━━━━━━━━━\n\n{report}"
    
    if DISCORD_WEBHOOK_URL:
        DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final_output[:1950]).execute()

if __name__ == "__main__":
    main()
