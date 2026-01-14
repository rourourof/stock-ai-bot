import os, requests, datetime, pytz, time
import yfinance as yf
from discord_webhook import DiscordWebhook

# === 環境変数チェック ===
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
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

def call_openrouter_xiaomi(prompt):
    model_name = "xiaomi/mimo-v2-flash:free"
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "あなたは金融アナリストです。日本語で回答してください。"},
            {"role": "user", "content": prompt}
        ]
    }

    for i in range(3):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content']
            elif res.status_code == 429:
                time.sleep(65)
        except:
            time.sleep(5)
    return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    
    # データの取得
    m_data = get_market_analysis()
    
    # AIへの依頼
    prompt = f"以下のデータを分析してレポートを書いてください：{m_data}"
    report = call_openrouter_xiaomi(prompt)
    
    # --- Discord送信内容の組み立て ---
    if not report:
        report = "【数値速報】AIが混雑しているため、生データのみ配信します。"

    # 数値データ一覧（AIが失敗してもこれだけは表示される）
    data_text = "\n".join([f"■{v['name']}: {v['close']} ({v['change_pct']}%)" for v in m_data.values()])
    
    final_output = (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"【市場レビュー】{now.strftime('%m/%d %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{data_text}\n\n"
        f"--- AIによる考察 ---\n"
        f"{report}"
    )
    
    # Discord送信実行
    if DISCORD_WEBHOOK_URL:
        print("Attempting to send to Discord...")
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final_output[:1950])
        response = webhook.execute()
        print(f"Discord Status Code: {response.status_code}")
    else:
        print("Error: DISCORD_WEBHOOK_URL is not set!")

if __name__ == "__main__":
    main()
