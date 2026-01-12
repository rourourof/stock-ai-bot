import os
import yfinance as yf
from newsapi import NewsApiClient
import google.generativeai as genai
from discordwebhook import Discord
import pandas as pd

# APIキーの設定（GitHub ActionsのSecretsから読み込み）
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 各種クライアントの初期化
genai.configure(api_key=GEMINI_API_KEY)
newsapi = NewsApiClient(api_key=NEWS_API_KEY)
discord = Discord(url=DISCORD_WEBHOOK_URL)

def get_stock_data(symbol):
    """株価データの取得"""
    stock = yf.Ticker(symbol)
    hist = stock.history(period="2d")
    if len(hist) < 2:
        return "データ取得失敗"
    last_close = hist['Close'].iloc[-1]
    prev_close = hist['Close'].iloc[-2]
    change = ((last_close - prev_close) / prev_close) * 100
    return f"{symbol}: ${last_close:.2f} ({change:+.2f}%)直近"

def main():
    # 44行目付近のエラー箇所：分析したいキーワードのリスト
    queries = ["US Stock Market", "S&P 500", "NVIDIA stock", "Apple stock"]
    
    # ニュースの取得
    all_news = ""
    for q in queries:
        top_headlines = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=3)
        for article in top_headlines['articles']:
            all_news += f"- {article['title']}\n"

    # Geminiによる分析
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    以下の米国株ニュースと情報を日本語で要約し、今後の市場予測を短くまとめてください。
    また、Discord投稿用に絵文字を交えて読みやすくしてください。

    【ニュース内容】
    {all_news}
    """
    
    response = model.generate_content(prompt)
    report = response.text

    # Discordへ送信
    discord.post(content=report)
    
    # 予測結果を保存（GitHub Actionsでのコミット用）
    with open("prediction.json", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    main()
