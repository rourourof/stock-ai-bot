import os
import yfinance as yf
from newsapi import NewsApiClient
import google.generativeai as genai
from discord_webhook import DiscordWebhook
import pandas as pd

# APIキーの設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Geminiの初期化
genai.configure(api_key=GEMINI_API_KEY)

def main():
    # ニュースの検索キーワード
    queries = ["US Stock Market", "S&P 500", "NVIDIA stock"]
    
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    all_news = ""
    
    try:
        for q in queries:
            top_headlines = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=3)
            for article in top_headlines['articles']:
                all_news += f"- {article['title']}\n"
    except Exception as e:
        all_news = "ニュース取得中にエラーが発生しました。"

    # Geminiによる分析
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"以下のニュースを日本語で要約し、投資家向けのコメントを絵文字付きで作成して：\n{all_news}"
    
    response = model.generate_content(prompt)
    report = response.text

    # Discordへ送信 (ライブラリ名を修正)
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
    webhook.execute()
    
    # 保存
    with open("prediction.json", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    main()
