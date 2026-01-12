import os
import yfinance as yf
from newsapi import NewsApiClient
import google.generativeai as genai
from discord_webhook import DiscordWebhook

# APIキーの設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 【重要】APIバージョンを安定版の 'v1' に強制指定して初期化
from google.generativeai import client
genai.configure(api_key=GEMINI_API_KEY, transport='grpc')

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

    # 2. Gemini AI による分析（安定版 v1 を使用）
    try:
        # モデル名の前に何もつけず、もっとも標準的な名前で呼び出します
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash'
        )
        
        prompt = f"以下の米国株ニュースを日本語で簡潔に要約し、投資アドバイスを絵文字付きで作成して：\n{all_news}"
        
        # 実行
        response = model.generate_content(prompt)
        report = response.text
    except Exception as e:
        # これでもダメな場合、利用可能なモデル名をログに出力してDiscordに送る
        try:
            available_models = [m.name for m in genai.list_models()]
            report = f"AI分析エラー。利用可能モデルリスト: {available_models} \n詳細: {str(e)}"
        except:
            report = f"AI分析エラー詳細: {str(e)}"

    # 3. Discordへの通知
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
    webhook.execute()

if __name__ == "__main__":
    main()
