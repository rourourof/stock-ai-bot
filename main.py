import os, requests, datetime, pytz, time
import yfinance as yf
from discord_webhook import DiscordWebhook

# === 環境変数 ===
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_analysis():
    # データ取得ロジック（そのまま）
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

def call_openrouter_high_inference(prompt):
    # 【2026年最強の無料推論モデル】DeepSeek-R1 を指定
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-r1:free", 
        "messages": [
            {"role": "system", "content": "あなたは金融市場を30年監視してきたプロのストラテジストです。数値の裏にある投資家心理を言語化することを得意としています。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.6 # 思考型モデルなので、少し柔軟性を持たせると良い文章になります
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=90) # 推論に時間がかかるため長めに設定
        data = res.json()
        # DeepSeek-R1は <think>タグの中に思考過程が入ることがあるため、結果のみを抽出
        content = data['choices'][0]['message']['content']
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        return content
    except:
        return None

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    m_data = get_market_analysis()
    
    time_tag = "06:07" if 5 <= now.hour <= 11 else "18:07"
    
    # 推論を引き出すためのプロンプト
    prompt = f"""
以下の市場データを多角的に分析し、深みのある日本語レポートを作成してください。
【データ】{m_data}

【執筆ガイドライン】
1. NVIDIAの動きが半導体指数(SOX)全体にどう波及しているか、その相関性を論理的に記述せよ。
2. 単なる数値の羅列ではなく「市場が何を懸念し、何を期待しているか」という心理面を推論せよ。
3. 今後の展開として「強気・弱気・中立」の3つの分岐点をプロの視点で提示せよ。
4. 文体は硬派なレポート形式。投資助言ではない免責事項を必ず含めること。
"""

    report = call_openrouter_high_inference(prompt)
    
    if not report:
        report = "【数値速報】AI推論エンジンが混雑しているため、データのみ配信します。\n" + str(m_data)

    final_output = f"━━━━━━━━━━━━━━━━━━\n【市場深層レポート】{time_tag} JST\n━━━━━━━━━━━━━━━━━━\n\n{report}\n\n配信時刻：{now.strftime('%Y-%m-%d %H:%M')} JST"
    
    if DISCORD_WEBHOOK_URL:
        # DeepSeekは長文になりやすいため、分割送信を徹底
        for i in range(0, len(final_output), 1900):
            DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=final_output[i:i+1900]).execute()
            time.sleep(1.5)

if __name__ == "__main__":
    main()
