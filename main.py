import os, requests, datetime, pytz, time
import yfinance as yf
from discord_webhook import DiscordWebhook

# === 環境変数（GitHub Secretsから読み込み） ===
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_analysis():
    # 以前の判定ロジックをそのまま維持
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
    # 先ほど「こんにちは」が成功したアカウントなら、このモデルが動きます
    # 2026年現在の最も標準的なモデル名に設定
    model = "gemini-1.5-flash" 
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 3000},
        "safetySettings": [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        data = response.json()
        if response.status_code == 200:
            return data['candidates'][0]['content']['parts'][0]['text']
        else:
            # エラーが出た場合、モデル名を 2.0-flash に変えて一度だけ再試行
            print(f"Retrying with 2.0-flash... (Error: {response.status_code})")
            url_alt = url.replace("gemini-1.5-flash", "gemini-2.0-flash")
            res_alt = requests.post(url_alt, json=payload, timeout=60)
            if res_alt.status_code == 200:
                return res_alt.json()['candidates'][0]['content']['parts'][0]['text']
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    m_data = get_market_analysis()
    
    time_tag = "06:07" if 5 <= now.hour <= 11 else "18:07"
    
    prompt = f"""
あなたはプロの市場ストラテジストです。
以下のデータから、NVDAとSOXを同等の比重で分析した重厚なレビューを日本語で執筆してください。
【データ】{m_data}
【条件】シナリオ提示または検証。投資助言ではない旨を末尾に記載。冷徹なトーンで。
"""

    report = call_gemini_stable(prompt)
    
    if not report:
        report = "【市場概況】AI生成制限中のため数値のみ配信します。\n\n" + str(m_data)

    final_output = f"━━━━━━━━━━━━━━━━━━\n【米国株 市場レビュー】{time_tag} JST\n━━━━━━━━━━━━━━━━━━\n\n{report}\n\n配信時刻：{now.strftime('%Y-%m-%d %H:%M')} JST"
    
    if DISCORD_WEBHOOK_URL:
        # Discordの2000文字制限対策
        for i in range(0, len(final_output), 1900):
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final_output[i:i+1900]).execute()
            time.sleep(1)

if __name__ == "__main__":
    main()
