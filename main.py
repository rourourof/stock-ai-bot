import os, requests, datetime, pytz, time
import yfinance as yf
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === API設定（GitHub Secrets） ===
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
                "range_judgment": "上抜け" if curr['Close'] > prev['High'] else ("下抜け" if curr['Close'] < prev['Low'] else "レンジ内"),
                "high": round(curr['High'], 2), "low": round(curr['Low'], 2)
            }
        except: pass
    if "NVDA" in results and "^SOX" in results:
        diff = results["NVDA"]["change_pct"] - results["^SOX"]["change_pct"]
        results["NVDA"]["relative_strength"] = f"対SOX {diff:+.2f}% ({'強' if diff>0 else '弱'})"
    return results

def fetch_news():
    try:
        res = NewsApiClient(api_key=NEWS_API_KEY).get_everything(q="NVIDIA OR 'Federal Reserve' OR Semiconductor", language='en', sort_by='publishedAt', page_size=12)
        return "\n".join([f"・{a['title']} ({a['source']['name']})" for a in res.get('articles', [])])
    except: return "ニュース取得制限中"

def call_gemini(prompt):
    # Gemini 1.5 Flash (安定・高速)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3000},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    try:
        res = requests.post(url, json=payload, timeout=100)
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    if now.weekday() == 5: return # 土曜休止
    
    is_morning = 5 <= now.hour <= 11
    time_tag = "06:07" if is_morning else "18:07"
    
    m_data = get_market_analysis()
    n_data = fetch_news()

    role_text = "前日の検証・振り返り" if is_morning else "当日相場の整理＋今夜の3シナリオ提示"
    prompt = f"""ストラテジストとして執筆せよ。
    【役割】{role_text}
    【絶対条件】NVDAとSOXを同一比重で分析。ニュースは織り込み済みかを評価。政治・金融政策は短期・中期・トレンドを明示。
    【数値データ】{m_data}
    【最新ニュース】{n_data}
    トーンは冷徹かつ簡潔に。"""

    report = call_gemini(prompt)
    if not report:
        report = "※AI生成制限につき数値のみ配信\n\n" + "\n".join([f"■{v['name']}: {v['close']} ({v['change_pct']}%)\n 判定:{v['range_judgment']}" for v in m_data.values()])

    final = f"━━━━━━━━━━━━━━━━━━\n【米国株 市場レビュー】{time_tag} JST\n（米国株 / 半導体・NVDA中心）\n━━━━━━━━━━━━━━━━━━\n\n{report}\n\n━━━━━━━━━━━━━━━━━━\n配信時刻：{now.strftime('%Y-%m-%d %H:%M')} JST\n※ 投資助言ではありません"
    
    for i in range(0, len(final), 1950):
        DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final[i:i+1950]).execute()
        time.sleep(1)

if __name__ == "__main__":
    main()
