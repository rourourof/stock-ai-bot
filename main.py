import os
import requests
import datetime
import pytz
import yfinance as yf
import pandas as pd
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# === 設定 ===
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_market_data(is_morning):
    """株価・先物・テクニカル指標の取得"""
    # 取得銘柄：NVDA, SOX指数(^SOX), S&P500先物(ES=F), ナスダック先物(NQ=F)
    targets = {"NVDA": "NVIDIA", "^SOX": "半導体指数", "ES=F": "S&P500先物", "NQ=F": "ナスダック100先物"}
    
    report_data = ""
    for ticker, name in targets.items():
        try:
            t = yf.Ticker(ticker)
            # 振り返りのために少し長めに取得
            hist = t.history(period="10d")
            if len(hist) < 5: continue
            
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            
            # テクニカル指標
            sma5 = hist['Close'].rolling(window=5).mean().iloc[-1]
            high_52w = hist['High'].max()
            
            report_data += f"\n【{name} ({ticker})】\n"
            report_data += f"- 現在値/終値: {curr['Close']:.2f} (前日比: {change_pct:+.2f}%)\n"
            report_data += f"- 出来高: {curr['Volume']:,}\n"
            report_data += f"- 5日移動平均乖離: {((curr['Close']-sma5)/sma5)*100:+.2f}%\n"
            if is_morning:
                report_data += f"- 安値からの戻り: {((curr['Close']-curr['Low'])/curr['Low'])*100:+.2f}%\n"
        except: pass
    return report_data

def fetch_news_detailed():
    """ニュースを詳細に取得"""
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    queries = ["NVIDIA AI", "US Stock Market Fed", "US China Politics", "Semiconductor industry"]
    collected = ""
    for q in queries:
        try:
            res = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', page_size=5)
            for art in res.get('articles', []):
                content = art.get('description') or art.get('content') or ""
                collected += f"■SOURCE: {art['source']['name']}\nTITLE: {art['title']}\nDETAIL: {content[:400]}\n\n"
        except: pass
    return collected

def main():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    day = now.strftime('%A')
    hour = now.hour
    
    is_morning = 5 <= hour <= 11
    market_info = get_detailed_market_data(is_morning)
    news_info = fetch_news_detailed()

    # モードと特定の指示の設定
    if day == "Sunday":
        mode = "日曜版：【今週の総括】全ニュースと値動きの徹底解剖"
        time_instruction = "1週間の全材料を振り返り、来週の戦略を10分読めるボリュームで解説してください。"
    elif is_morning:
        mode = "平日朝：【答え合わせと分析】昨夜の予想検証と要因特定"
        time_instruction = """
        昨夜の夕方の予測と、実際の市場の動き（終値）を照らし合わせ、以下の点に重点を置いてください：
        1. 予測は的中したか？乖離した場合はその原因。
        2. どのニュースが市場を動かす「主因」となり、どのニュースが「無視（織り込み済み）」されたか。
        3. NVIDIAと半導体指数のテクニカル的な引け方の評価。
        """
    else:
        mode = "平日夕：【今夜のシナリオ予想】先物・テクニカル・材料から読む期待値"
        time_instruction = """
        現在の先物市場の動きとテクニカル指標を組み合わせ、今夜の開場から引けまでの値動きを予測してください：
        1. 先物（ES=F, NQ=F）の動きから読み取る市場心理。
        2. 今夜のメイン、強気、弱気の3シナリオ。
        3. NVIDIAが今夜突破すべき上値抵抗線と、守るべき支持線の具体的提示。
        """

    prompt = f"""
あなたは米国株のシニアアナリストとして、10分かけて読むに値する圧倒的な分量のレポート（約5000文字）を執筆してください。

【本日の配信モード】: {mode}

【市場データ】: {market_info}
【詳細ニュースソース】: {news_info}

【必須構成】:
1. **影響度ランキング**：ニュースを市場への影響度順（NVDA/半導体/金利/政治等）に格付けし、詳細に解説。
2. **NVIDIA & 半導体別枠分析**：先物データと直近の出来高、移動平均線、乖離率を用いたテクニカル分析。
3. **政治・地政学・AI・対中政策**：政治家の発言や政策が特定セクターに与える影響。
4. **実際のニュース欄**：詳細を割愛せず、ソースを明示して整理。
5. **答え合わせ or シナリオ予測（最重要）**:
   {time_instruction}

【執筆ルール】:
- 「割愛」「詳細不明」は禁止。プロの洞察ですべての行を埋めること。
- 絵文字を多用し、読み手が興奮するような熱量と、冷静な論理分析を両立させること。
- 聞かなかったニュース、織り込み済みニュースのセクションを必ず設けること。
"""

    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8
            },
            timeout=1
