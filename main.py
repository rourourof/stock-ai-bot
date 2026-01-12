import os
import yfinance as yf
from newsapi import NewsApiClient
from google import genai
from discord_webhook import DiscordWebhook

# APIキーの設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def main():
    # 1. ニュースの取得（トークン節約のため件数を絞る）
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    queries = ["US Stock Market"]
    all_news = ""
    
    try:
        result = newsapi.get_everything(q="US Stock Market", language='en', sort_by='relevancy', page_size=5)
        for article in result.get('articles', []):
            all_news += f"- {article['title']}\n"
    except:
        all_news = "ニュース取得制限中"

    # 2. Gemini AI による分析（1.5-flashを明示的に指定）
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"以下の米国株ニュースを日本語で3行で要約し、投資コメントを絵文字付きで作成して：\n{all_news}"
    
    try:
        # gemini-2.0が制限されているため、安定している gemini-1.5-flash を使用
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=prompt
        )
        report = response.text
    except Exception as e:
        # クォータエラーが起きた場合の説明を分かりやすく
        if "429" in str(e):
            report = "【エラー】Gemini APIの無料枠制限（1分間あたりの回数制限）に達しました。少し時間を置いてから再度実行してください。"
        else:
            report = f"AI分析エラー: {str(e)}"

    # 3. Discordへの通知
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
    webhook.execute()

if __name__ == "__main__":
    main()
