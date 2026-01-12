import os
import yfinance as yf
from newsapi import NewsApiClient
import google.generativeai as genai  # 安定版のライブラリに戻します
from discord_webhook import DiscordWebhook

# APIキーの設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Geminiの初期化
genai.configure(api_key=GEMINI_API_KEY)

def main():
    # 1. ニュースの取得
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    all_news = ""
    try:
        result = newsapi.get_everything(q="US Stock Market", language='en', sort_by='relevancy', page_size=5)
        for article in result.get('articles', []):
            all_news += f"- {article['title']}\n"
    except:
        all_news = "ニュース取得制限中"

    # 2. Gemini AI による分析（404エラーが出にくい旧ライブラリ形式）
    try:
        # 2026年でも安定して動く1.5-flashを指定
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"以下の米国株ニュースを日本語で簡潔に要約し、投資アドバイスを絵文字付きで作成して：\n{all_news}"
        
        response = model.generate_content(prompt)
        report = response.text
    except Exception as e:
        report = f"AI分析エラー詳細: {str(e)}"

    # 3. Discordへの通知
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
    webhook.execute()

if __name__ == "__main__":
    main()
