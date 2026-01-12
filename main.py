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
    # 1. ニュースの取得（News API）
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    queries = ["US Stock Market", "S&P 500", "NVIDIA"]
    all_news = ""
    
    try:
        for q in queries:
            result = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=2)
            if 'articles' in result:
                for article in result['articles']:
                    all_news += f"- {article['title']}\n"
    except Exception as e:
        all_news = "ニュースの取得に失敗しました。"

    # 2. Gemini AI による分析（404エラー対策済み）
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"以下の米国株ニュースを日本語で要約し、明日の予測を絵文字付きで楽しくレポートして：\n{all_news}"
    
    try:
        # モデル名の指定に 'models/' を付与することで 404 エラーを回避します
        response = client.models.generate_content(
            model='models/gemini-1.5-flash', 
            contents=prompt
        )
        report = response.text
    except Exception as e:
        # エラー詳細もDiscordに送るようにして、デバッグしやすくします
        report = f"AI分析中にエラーが発生しました: {str(e)}"

    # 3. Discordへの通知
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
    webhook.execute()
    
    # 4. 実行ログを保存
    with open("prediction.json", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    main()
