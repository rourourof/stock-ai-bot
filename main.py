import os, requests, datetime, pytz, time
import yfinance as yf
from discord_webhook import DiscordWebhook

# === 環境変数 ===
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

def call_ai_with_fallback(prompt):
    # 無料で使える有力モデルのリスト（上から順に試します）
    # 2026年現在、比較的空きやすい順番です
    models = [
        "google/gemini-2.0-flash-exp:free", # 最新かつ高性能
        "xiaomi/mimo-v2-flash:free",        # 意外と穴場
        "meta-llama/llama-3.1-8b-instruct:free" # 最後の砦
    ]
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    for model in models:
        try:
            print(f"Trying {model}...")
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5
            }
            res = requests.post(url, headers=headers, json=payload, timeout=40)
            
            if res.status_code == 200:
                print(f"Success with {model}!")
                return res.json()['choices'][0]['message']['content']
            else:
                print(f"Failed {model}: {res.status_code}")
                # 混雑(429)なら少し待って次へ
                time.sleep(2)
        except Exception as e:
            print(f"Error connecting to {model}: {e}")
            continue
            
    return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    m_data = get_market_analysis()
    
    # AIが答えやすいように「指示」を極限までシンプルにしました
    prompt = f"プロの投資家として、以下のデータを日本語で簡潔に分析せよ（200文字以内）：{m_data}"

    report = call_ai_with_fallback(prompt)
    
    # 最終的な表示内容
    header = f"━━━━━━━━━━━━━━━━━━\n【市場レビュー】 {now.strftime('%m/%d %H:%M')}\n━━━━━━━━━━━━━━━━━━"
    data_text = "\n".join([f"■{v['name']}: {v['close']} ({v['change_pct']}%)" for v in m_data.values()])
    
    footer = "--- AI Analysis ---\n"
    if report:
        footer += report
    else:
        footer += "※全ての無料モデルが混雑中のため、文章生成をスキップしました。"

    final_output = f"{header}\n\n{data_text}\n\n{footer}\n\n※投資助言ではありません。"
    
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final_output[:1950])
        webhook.execute()
        print("Done!")

if __name__ == "__main__":
    main()
