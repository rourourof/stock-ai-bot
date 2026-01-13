import os, requests, datetime, pytz, time, feedparser
import yfinance as yf
import pandas as pd
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === API設定 ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# --- 1. Pythonによる数値・テクニカル判定 (AI判断禁止領域) ---
def get_market_data():
    tickers = {"NVDA": "NVIDIA", "^SOX": "半導体指数(SOX)", "^IXIC": "NASDAQ"}
    results = {}
    
    for sym, name in tickers.items():
        try:
            t = yf.Ticker(sym)
            df = t.history(period="40d")
            if len(df) < 22: continue
            
            curr, prev = df.iloc[-1], df.iloc[-2]
            vol_avg20 = df['Volume'].iloc[-21:-1].mean()
            
            # 数値ロジック判定
            results[sym] = {
                "name": name,
                "close": round(curr['Close'], 2),
                "change_pct": round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2),
                "high": round(curr['High'], 2), "low": round(curr['Low'], 2),
                "prev_high": round(prev['High'], 2), "prev_low": round(prev['Low'], 2),
                "volume": int(curr['Volume']),
                "vol_avg": int(vol_avg20),
                "vol_status": "平均以上" if curr['Volume'] > vol_avg20 else "平均以下",
                "range_judgment": "上抜け" if curr['Close'] > prev['High'] else ("下抜け" if curr['Close'] < prev['Low'] else "レンジ内")
            }
        except Exception as e: print(f"Data error {sym}: {e}")
    
    # 相対強弱判定
    if "NVDA" in results and "^SOX" in results:
        diff = results["NVDA"]["change_pct"] - results["^SOX"]["change_pct"]
        results["NVDA"]["relative_strength"] = f"対SOX {diff:+.2f}% ({'強' if diff>0 else '弱'})"
    
    return results

# --- 2. ニュース取得・分類 ---
def fetch_news():
    news_api = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    
    context = {"latest": "", "politics": ""}
    try:
        # 過去24時間（速報）
        res = news_api.get_everything(q="NVIDIA OR 'Federal Reserve' OR Semiconductor", language='en', sort_by='publishedAt', page_size=12)
        for art in res.get('articles', []):
            context["latest"] += f"・{art['title']} ({art['source']['name']})\n"
    except: pass
    return context

# --- 3. フォールバック生成 (AI失敗時用) ---
def fallback_report(m_data, time_tag):
    report = f"━━━━━━━━━━━━━━━━━━\n【米国株 市場レビュー】{time_tag} JST\n━━━━━━━━━━━━━━━━━━\n"
    report += "※システム制限により数値データのみ配信中\n\n"
    for k, v in m_data.items():
        report += f"■{v['name']}\n 価格:{v['close']} ({v['change_pct']}%)\n 出来高:{v['vol_status']}\n 判定:{v['range_judgment']}\n\n"
    return report

# --- 4. メインロジック ---
def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    
    # 土曜配信停止 / 月曜朝は金曜の検証
    if now.weekday() == 5: return 

    is_morning = 5 <= now.hour <= 11
    time_tag = "06:07" if is_morning else "18:07"
    
    m_data = get_market_data()
    n_data = fetch_news()

    # プロンプト構築（制約の塊）
    prompt = f"""
あなたはプロの機関投資家向けストラテジストです。
【米国株 市場レビュー】{time_tag} JST を執筆してください。

【絶対遵守事項】
1. NVIDIA(NVDA)と半導体セクター(^SOX)を「同一比重・同一分量」で分析すること。片方に偏ることは許されません。
2. ニュースの「織り込み済み」かどうかの評価を必ず含めること。
3. 政治・金融政策は「短期・中期・トレンド」の影響度を明示すること。
4. 提供された数値データ（価格・出来高・判定）は一文字も変えずに使用すること。

【役割】
{'18:07：当日相場の整理と、3つのシナリオ（上昇・横ばい・下落）提示。条件と崩れる条件を明記。' if not is_morning else '06:07：前日のシナリオ検証と見立てのズレ、今日修正すべき視点の提示。'}

【提供数値データ】
{m_data}
【実在ニュース】
{n_data['latest']}

【出力フォーマット】
指定された見出し、免責事項、配信時刻を厳守。
読了時間10分に相応しい情報密度で執筆せよ。
"""

    # AI呼び出し (Gemini 1.5 Flash - 安定性重視)
    try:
        headers = {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "google/gemini-1.5-flash", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=100)
        report = res.json()['choices'][0]['message']['content']
    except:
        report = fallback_report(m_data, time_tag)

    # 最終整形
    final_post = f"━━━━━━━━━━━━━━━━━━\n【米国株 市場レビュー】{time_tag} JST\n（米国株 / 半導体・NVDA中心）\n━━━━━━━━━━━━━━━━━━\n"
    final_post += report
    final_post += f"\n\n━━━━━━━━━━━━━━━━━━\n配信時刻：{now.strftime('%Y-%m-%d %H:%M')} JST\n※ 自動生成 / 投資助言ではありません"

    # Discord送信 (長文分割)
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content="temp")
    for i in range(0, len(final_post), 1950):
        webhook.content = final_post[i:i+1950]
        webhook.execute()
        time.sleep(1)

if __name__ == "__main__":
    main()
