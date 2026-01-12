import os
import json
import datetime
import pandas as pd
import yfinance as yf
from newsapi import NewsApiClient
import google.generativeai as genai
from discord_webhook import DiscordWebhook

# 1. 各種設定（GitHub Secretsから読み込み）
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

# Geminiの初期化
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 2. データ取得関数
def get_stock_metrics(ticker_symbol):
    """yfinanceを使用して株価とテクニカル指標を取得"""
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="1mo")
    if len(hist) < 2: return "データ取得失敗"
    
    last_close = hist['Close'].iloc[-1]
    prev_close = hist['Close'].iloc[-2]
    change_pct = ((last_close - prev_close) / prev_close) * 100
    avg_vol = hist['Volume'].mean()
    last_vol = hist['Volume'].iloc[-1]
    vol_ratio = last_vol / avg_vol
    
    return {
        "price": round(last_close, 2),
        "change_pct": round(change_pct, 2),
        "volume_ratio": round(vol_ratio, 2),
        "raw_data": hist.tail(5).to_string()
    }

def get_market_news():
    """NewsAPIを使用して最新ニュースを取得"""
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    # NVDA, 半導体, 金利, 政治に関するクエリ
    queries =
    all_headlines =
    for q in queries:
        top_headlines = newsapi.get_top_headlines(q=q, language='en', country='us')
        for art in top_headlines['articles']:
            all_headlines.append(f"- {art['title']} ({art['source']['name']})")
    return "\n".join(list(set(all_headlines))[:20]) # 重複削除して20件

# 3. 状態管理（答え合わせ用）
PREDICTION_FILE = 'prediction.json'

def save_prediction(content):
    with open(PREDICTION_FILE, 'w', encoding='utf-8') as f:
        json.dump({"last_prediction": content, "date": str(datetime.date.today())}, f, ensure_ascii=False)

def load_prediction():
    if os.path.exists(PREDICTION_FILE):
        with open(PREDICTION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

# 4. Discord送信関数 (2000文字制限回避)
def send_to_discord(text):
    for i in range(0, len(text), 1900):
        chunk = text[i:i+1900]
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=chunk)
        webhook.execute()

# 5. メインロジック
def main():
    now_jst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    hour = now_jst.hour
    weekday = now_jst.weekday() # 0=月, 6=日

    # データの収集
    nvda_data = get_stock_metrics("NVDA")
    soxx_data = get_stock_metrics("SOXX")
    news_headlines = get_market_news()
    
    # 配信モードの判定
    is_sunday = (weekday == 6)
    mode = "朝の振り返り" if 5 <= hour <= 7 else "夕方の予測"
    if is_sunday: mode = "週間レポート"

    # AIへのプロンプト構築
    prediction_data = load_prediction()
    prev_prediction = prediction_data['last_prediction'] if prediction_data else "なし"

    prompt = f"""
    あなたは世界最高峰の金融アナリストです。以下のデータに基づき、日本人が読むのに10分かかる（約8,000文字以上）非常に詳細な米国株投資レポートを日本語で作成してください。
    
    【現在の市場データ】
    - NVIDIA(NVDA): 価格 {nvda_data['price']}, 前日比 {nvda_data['change_pct']}%, 出来高比 {nvda_data['volume_ratio']}倍
    - 半導体ETF(SOXX): 価格 {soxx_data['price']}, 前日比 {soxx_data['change_pct']}%, 出来高比 {soxx_data['volume_ratio']}倍
    - 最新ニュース概略:
    {news_headlines}

    【レポート構成ルール】
    1. 【株式市場への影響度ランキング】: ニュースを「金利」「NVDA」「半導体セクター」「米国政治」に分類し、影響度の高い順に理由付きで詳述。
    2. 【実際の最新ニュース詳細】: 提供したニュースを深掘りし、市場のコンセンサスを分析。
    3. 【米国政治・AI・対中政策】: 政治家の発言、AI規制、中国への輸出規制がもたらす長期的影響を分析。
    4. 【NVIDIA & 半導体セクター テクニカル分析】: NVDAとSOXXを同じ比重で扱い、出来高と値動きから投資家心理を読み解く。
    5. 【シナリオ分析】:
       - 18:00の場合: 今夜のNY市場の値動きを3つのシナリオ（強気・弱気・横ばい）で予想。
       - 06:00の場合: 前夜の予想「{prev_prediction}」に対する答え合わせ。的中・外れの理由、織り込み済みだったニュース、無視された材料を詳細に検証。
       - 日曜日の場合: 今週全体の総括と来週の展望。

    ※注意: 各項目で「なぜそうなるのか」という理由を必ず3段落以上で深く論理的に説明してください。8,000文字以上の圧倒的な情報量を維持してください。
    """

    # AIで文章生成
    response = model.generate_content(prompt)
    report_text = response.text

    # 18:00の実行なら予測を保存
    if mode == "夕方の予測":
        save_prediction(report_text[:1000]) # 冒頭の要約部分のみ保存

    # 送信
    send_to_discord(f"🚀 **米国株 AI インテリジェンス・レポート ({mode})** 🚀\n" + report_text)

if __name__ == "__main__":
    main()
