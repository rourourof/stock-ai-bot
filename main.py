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
    # 2026年現在、最も接続が安定している「正式版」モデル名
    # exp(実験版)を避け、安定版を指定します
    model_name = "gemini-2.0-flash" 
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GOOGLE_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 2500},
        "safetySettings": [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }

    # クォータ制限(Limit 0)対策：20秒待機して再試行
    for i in range(2):
        try:
            print(f"Connecting to Gemini (Attempt {i+1})...")
            response = requests.post(url, json=payload, timeout=60)
            data = response.json()
            
            if response.status_code == 200:
                return data['candidates'][0]['content']['parts'][0]['text']
            
            # 429(枠不足)が出た場合、30秒待つ
            if response.status_code == 429:
                print("Quota limit hit. Waiting 30 seconds...")
                time.sleep(30)
                continue
            else:
                print(f"API Error: {data.get('error', {}).get('message')}")
                break
        except Exception as e:
            print(f"Exception: {e}")
            time.sleep(5)
    return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    m_data = get_market_analysis()
    
    time_tag = "06:07" if 5 <= now.hour <= 11 else "18:07"
    
    prompt = f"""
機関投資家向けストラテジストとして、以下のデータを分析し、
NVDAとSOXを対等に扱った、冷徹で重厚なレビューを日本語で執筆してください。
【データ】{m_data}
【条件】{'前日の取引検証' if time_tag == "06:07" else '今夜の相場シナリオ提示'}。
末尾に「※投資助言ではありません」を付与。
"""

    report = call_gemini_stable(prompt)
    
    if not report:
        report = "【市場概況】AI接続が一時的に制限されたため、数値のみ配信します。\n\n"
        for v in m_data.values():
            report += f"■{v['name']}: {v['close']} ({v['change_pct']}%)\n 判定:{v['range_judgment']}\n"

    final_output = f"━━━━━━━━━━━━━━━━━━\n【米国株 市場レビュー】{time_tag} JST\n━━━━━━━━━━━━━━━━━━\n\n{report}\n\n配信時刻：{now.strftime('%Y-%m-%d %H:%M')} JST"
    
    if DISCORD_WEBHOOK_URL:
        # Discordの文字数制限対策
        for i in range(0, len(final_output), 1900):
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final_output[i:i+1900]).execute()
            time.sleep(1)

if __name__ == "__main__":
    main()
