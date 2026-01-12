import os
import yfinance as yf
from newsapi import NewsApiClient
from genai import Client  # 最新の google-genai ライブラリ
from discord_webhook import DiscordWebhook

# APIキーの設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def main():
    # 1. ニュースの取得
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    queries = ["US Stock Market", "NVIDIA stock"]
    all_news = ""
    
    try:
        for q in queries:
            result = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=2)
            for article in result['articles']:
                all_news += f"- {article['title']}\n"
    except:
        all_news = "ニュースを取得できませんでした。"

    # 2. Geminiによる分析 (最新のClient方式)
    # モデル名を 'gemini-1.5-flash' に修正
    client = Client(api_key=GEMINI_API_KEY)
    prompt = f"以下のニュースを日本語で要約し、投資コメントを絵文字付きで作って：\n{all_news}"
    
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=prompt
        )
        report = response.text
    except Exception as e:
        report = f"AI分析中にエラーが発生しました: {str(e)}"

    # 3. Discordへ送信
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
    webhook.execute()
    
    # 4. 結果を保存
    with open("prediction.json", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    main()
