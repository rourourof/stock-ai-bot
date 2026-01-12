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
    # 1. ニュースの取得
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    queries = ["US Stock Market", "NVIDIA"]
    all_news = ""
    
    try:
        for q in queries:
            result = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=2)
            for article in result.get('articles', []):
                all_news += f"- {article['title']}\n"
    except Exception:
        all_news = "ニュースの取得に失敗しました。"

    # 2. Gemini AI による分析（404エラー対策）
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"以下の米国株ニュースを日本語で要約し、投資家へのアドバイスを絵文字付きで作成して：\n{all_news}"
    
    try:
        # SDKの内部挙動に合わせて、あえて 'models/' を付けないシンプルな名前で実行します。
        # もしこれでもダメな場合は 'gemini-2.0-flash' に自動で切り替わるようにします。
        try:
            response = client.models.generate_content(
                model='gemini-1.5-flash', 
                contents=prompt
            )
        except:
            # 万が一の予備モデル指定
            response = client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=prompt
            )
        report = response.text
    except Exception as e:
        report = f"AI分析エラー詳細: {str(e)}"

    # 3. Discordへの通知
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
    webhook.execute()

if __name__ == "__main__":
    main()
