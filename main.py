import os, requests, datetime, pytz, time
import yfinance as yf
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === 設定（GitHub Secrets） ===
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_analysis():
    tickers = {"NVDA": "NVIDIA", "^SOX": "半導体指数(SOX)", "^IXIC": "NASDAQ"}
    results = {}
    for sym, name in tickers.items():
        try:
            df = yf.Ticker(sym).history(period="40d")
            if len(df) < 22: continue
            curr, prev = df.iloc[-1], df.iloc[-2]
            vol_avg20 = df['Volume'].iloc[-21:-1].mean()
            results[sym] = {
                "name": name, "close": round(curr['Close'], 2),
                "change_pct": round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2),
                "vol_status": "平均以上" if curr['Volume'] > vol_avg20 else "平均以下",
                "range_judgment": "上抜け" if curr['Close'] > prev['High'] else ("下抜け" if curr['Close'] < prev['Low'] else "レンジ内")
            }
        except: pass
    return results

def call_gemini_official(prompt):
    if not GOOGLE_API_KEY:
        print("GOOGLE_API_KEYが設定されていません")
        return None
    
    # 【重要】エンドポイントURLをこの形式（モデル名を含むパス）に固定します
    # v1beta を使用することで最新の flash モデルへのアクセスを確実にします
    model_name = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GOOGLE_API_KEY}"
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 3000
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=120)
        data = res.json()
        
        if 'error' in data:
            print(f"Gemini API Error: {data['error'].get('message')}")
            # もし1.5-flashがダメと言われたら、汎用モデル名にフォールバックするログ
            print("Tip: API StudioでGemini 1.5 Flashが有効化されているか確認してください。")
            return None
            
        if 'candidates' in data and len(data['candidates']) > 0:
            candidate = data['candidates'][0]
            if 'content' in candidate:
                return candidate['content']['parts'][0]['text']
        return None
    except Exception as e:
        print(f"Request Exception: {e}")
        return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    if now.weekday() == 5: return # 土曜休止
    
    time_tag = "06:07" if 5 <= now.hour <= 11 else "18:07"
    m_data = get_market_analysis()
    
    prompt = f"""
あなたはプロの機関投資家向けストラテジストです。
以下の市場データを分析し、NVDAと半導体指数(SOX)を同一比重で扱ったレビューを作成してください。
【データ】{m_data}
【条件】
1. 数値は提供されたものを厳守。
2. 『18:07：シナリオ提示』または『06:07：前日検証』の視点で執筆。
3. 最後に「※投資助言ではありません」を付与。
"""

    report = call_gemini_official(prompt)
    
    # 失敗時のフォールバック（必ず投稿する）
    if not report:
        report = "【市場概況】数値データを配信します。\n\n"
        for v in m_data.values():
            report += f"■{v['name']}: {v['close']} ({v['change_pct']}%)\n 出来高:{v['vol_status']} / 判定:{v['range_judgment']}\n"
    
    final_output = f"━━━━━━━━━━━━━━━━━━\n【米国株 市場レビュー】{time_tag} JST\n（米国株 / 半導体・NVDA中心）\n━━━━━━━━━━━━━━━━━━\n\n{report}\n\n配信時刻：{now.strftime('%Y-%m-%d %H:%M')} JST"
    
    if DISCORD_WEBHOOK_URL:
        for i in range(0, len(final_output), 1950):
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final_output[i:i+1950]).execute()
            time.sleep(1)

if __name__ == "__main__":
    main()
