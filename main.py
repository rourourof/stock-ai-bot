import os
import requests
import datetime
import pytz
import yfinance as yf
import time
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === 設定 ===
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_data():
    """ yfinanceを使用して最新の2026年1月の価格データを取得 """
    targets = {"NVDA": "NVIDIA", "^SOX": "半導体指数", "ES=F": "S&P500先物", "NQ=F": "ナスダック100先物"}
    report_data = ""
    for ticker, name in targets.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if len(hist) < 2: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            report_data += f"銘柄:{name}({ticker}) 価格:{curr['Close']:.2f} 前日比:{change_pct:+.2f}%\n"
        except: pass
    return report_data

def fetch_news():
    """ 2026年1月の最新ニュースのみを厳選取得 """
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    # 物理的に過去のニュースが入らないよう、直近2日以内に限定
    start_date = (now - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    
    collected = ""
    # 検索ワードに「2026」を強制付与
    for q in ["NVIDIA 2026", "US Stock 2026"]:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', from_param=start_date, page_size=3)
            for art in res.get('articles', []):
                collected += f"・日時:{art['publishedAt']} タイトル:{art['title']}\n"
        except: pass
    return collected

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    current_jst = now.strftime('%Y/%m/%d %H:%M')
    is_morning = 5 <= now.hour <= 11
    
    market_info = get_market_data()
    news_info = fetch_news()

    # --- プロンプトを1回に凝縮し、エラーを防ぎつつ長文を出す指示 ---
    # 2024年の話を絶対にさせないための「システム命令」を強化
    prompt = f"""
【最優先指令】
現在は 2026年1月12日 です。あなたは2026年のシニアストラテジストです。
2024年や2025年の話は「歴史」としてのみ扱い、今の市場分析には絶対に使用しないでください。
提供する「2026年のリアルタイムデータ」のみに基づき、プロの投資レポートを作成してください。

【構成テンプレート】※以下の項目ごとに別枠を設け、各枠を3段落以上で詳しく書くこと
1. **2026年最新ニュース影響度格付け**：提供されたニュースの市場インパクトを順位付け。
2. **NVIDIA別枠テクニカル分析**：2026年1月の最新価格と出来高から見た攻防。
3. **半導体関連・AI・対中政策別枠**：地政学リスクとAI成長の現状。
4. **{'朝の答え合わせ' if is_morning else '今夜のシナリオ予想'}**：
   - {'昨夜の予測的中判定と、織り込み済みニュースの峻別' if is_morning else '先物データを用いた今夜の具体的3シナリオ'}
5. **実際のニュース一覧**：日付を明記。

【執筆スタイル】
- 読むのに10分かかる圧倒的な密度と文字数を目指してください。
- 絵文字を多用し、投資家のマインドを揺さぶる情熱的なトーン。
- 「割愛」「詳細不明」はプロとして禁止。

最新データ:
{market_info}
最新ニュース(2026年1月):
{news_info}
"""

    try:
        # 1回のリクエストに全力を注ぐ（分割せず、タイムアウトを長く取る）
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/my-stock-ai"},
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=180
        )
        report = res.json()['choices'][0]['message']['content']
    except Exception as e:
        report = f"⚠️ AIレポート生成エラー: {str(e)}\n(OpenRouterの無料枠制限が非常に厳しくなっています。時間を空けて再度お試しください。)"

    if DISCORD_WEBHOOK_URL:
        # 分割送信
        chunks = [report[i:i+1900] for i in range(0, len(report), 1900)]
        for chunk in chunks:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": chunk})
            time.sleep(2)

if __name__ == "__main__":
    main()
