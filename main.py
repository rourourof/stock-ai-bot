import os, requests, datetime, pytz, time
import yfinance as yf
import pandas as pd
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === API設定（GitHub Secretsから取得） ===
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") # Google AI Studioで取得したキー
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# --- 1. Pythonによる数値・テクニカル判定 (AI判断禁止・絶対領域) ---
def get_market_analysis():
    tickers = {"NVDA": "NVIDIA", "^SOX": "半導体指数(SOX)", "^IXIC": "NASDAQ"}
    results = {}
    
    for sym, name in tickers.items():
        try:
            t = yf.Ticker(sym)
            df = t.history(period="40d")
            if len(df) < 22: continue
            
            curr, prev = df.iloc[-1], df.iloc[-2]
            vol_avg20 = df['Volume'].iloc[-21:-1].mean()
            
            results[sym] = {
                "name": name,
                "close": round(curr['Close'], 2),
                "change_pct": round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2),
                "high": round(curr['High'], 2), "low": round(curr['Low'], 2),
                "prev_high": round(prev['High'], 2), "prev_low": round(prev['Low'], 2),
                "vol_status": "平均以上" if curr['Volume'] > vol_avg20 else "平均以下",
                "range_judgment": "上抜け" if curr['Close'] > prev['High'] else ("下抜け" if curr['Close'] < prev['Low'] else "レンジ内"),
                "volume": int(curr['Volume']),
                "vol_avg": int(vol_avg20)
            }
        except: pass
    
    # 相対強弱判定
    if "NVDA" in results and "^SOX" in results:
        diff = results["NVDA"]["change_pct"] - results["^SOX"]["change_pct"]
        results["NVDA"]["relative_strength"] = f"対SOX {diff:+.2f}% ({'強' if diff>0 else '弱'})"
    
    return results

# --- 2. ニュース取得 ---
def fetch_news():
    context = ""
    if not NEWS_API_KEY: return "NewsAPIキー未設定"
    try:
        news_api = NewsApiClient(api_key=NEWS_API_KEY)
        res = news_api.get_everything(q="NVIDIA OR 'Federal Reserve' OR Semiconductor", language='en', sort_by='publishedAt', page_size=12)
        for art in res.get('articles', []):
            context += f"・{art['title']} ({art['source']['name']})\n"
    except: context = "ニュース取得制限中"
    return context

# --- 3. Google公式 Gemini API 呼び出し (高性能・安定版) ---
def call_gemini_official(prompt):
    if not GOOGLE_API_KEY: return None
    # Gemini 1.5 Flashを使用（高速・安定・無料枠大）
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3000}
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=120)
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"API Error: {e}")
        return None

# --- 4. フォールバック生成 ---
def fallback_report(m_data, time_tag):
    report = f"【自動生成レビュー：{time_tag}】\n※AI生成制限につき数値のみ配信\n\n"
    for k, v in m_data.items():
        report += f"■{v['name']}: {v['close']} ({v['change_pct']}%)\n 出来高:{v['vol_status']} / 判定:{v['range_judgment']}\n"
    return report

# --- 5. メイン処理 ---
def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    if now.weekday() == 5: return # 土曜は休止
    
    is_morning = 5 <= now.hour <= 11
    time_tag = "06:07" if is_morning else "18:07"
    
    m_data = get_market_analysis()
    n_data = fetch_news()

    # プロンプト構築（絶対条件を注入）
    role_instruction = (
        "【06:07 検証】前日のシナリオと現実の乖離、効いたニュース、見立てのズレ、今日修正すべき視点を論理的に記述せよ。"
        if is_morning else
        "【18:07 シナリオ】当日相場を整理し、上昇・横ばい・下落の3シナリオを提示せよ。条件と崩れる条件、NVDA/SOX両方への言及を必須とする。"
    )

    prompt = f"""
あなたはプロの機関投資家向けストラテジストです。
{role_instruction}

【絶対ルール】
1. NVDAとSOX指数を同一の比重で分析せよ。
2. ニュースは「市場は織り込み済みか」を必ず評価せよ。
3. 政治・金融政策は短期・中期・トレンドの影響を明示。
4. 提供された数値データ（価格・出来高・レンジ判定）を絶対とし、AIが数値を変えてはならない。

【市場データ】
{m_data}
【ニュース】
{n_data}

構成：
- 重要ファクト評価
- NVDA & 半導体セクター分析（数値・出来高・相対比較含む）
- {time_tag} 専用セクション（シナリオまたは検証）
- 米国政治・金融政策の独立セクション
"""

    report = call_gemini_official(prompt)
    if not report:
        report = fallback_report(m_data, time_tag)

    # 最終フォーマット成形
    final_output = f"━━━━━━━━━━━━━━━━━━\n【米国株 市場レビュー】{time_tag} JST\n（米国株 / 半導体・NVDA中心）\n━━━━━━━━━━━━━━━━━━\n\n"
    final_output += report
    final_output += f"\n\n━━━━━━━━━━━━━━━━━━\n配信時刻：{now.strftime('%Y-%m-%d %H:%M')} JST\n※ 自動生成 / 投資助言ではありません"

    # Discord送信（長文分割対応）
    if DISCORD_WEBHOOK_URL:
        for i in range(0, len(final_output), 1950):
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final_output[i:i+1950]).execute()
            time.sleep(1)

if __name__ == "__main__":
    main()
