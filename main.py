import os
import yfinance as yf
from newsapi import NewsApiClient
import google.generativeai as genai
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
        # 検索範囲を少し広げて確実にニュースを拾うように調整
        result = newsapi.get_everything(q="US Stock Market news", language='en', sort_by='publishedAt', page_size=5)
        for article in result.get('articles', []):
            all_news += f"- {article['title']}\n"
    except:
        all_news = "ニュース取得に失敗しました。"

    # 2. Gemini AI による分析（最も見つかりやすいモデル名に修正）
    try:
        # 'gemini-1.5-flash' が見つからないと言われるため、
        # より広範にサポートされている 'models/gemini-1.5-flash' または
        # 最新版を指す 'gemini-1.5-flash-latest' を試します。
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        prompt = f"以下の米国株ニュースを日本語で要約し、明日の予測を絵文字付きで作成して：\n{all_news}"
        
        response = model.generate_content(prompt)
        report = response.text
    except Exception as e:
        # 万が一の予備：さらに古い安定版を指定
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            report = response.text
        except:
            report = f"AI分析エラー（モデルが見つかりません）: {str(e)}"

    # 3. Discordへの通知
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
    webhook.execute()

if __name__ == "__main__":
    main()
