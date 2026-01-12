import os
import requests
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# 環境変数から取得
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def main():
    # 1. ニュースの取得
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    all_news = ""
    try:
        result = newsapi.get_everything(q="US Stock Market", language='en', sort_by='relevancy', page_size=3)
        for article in result.get('articles', []):
            all_news += f"- {article['title']}\n"
    except:
        all_news = "ニュース取得失敗"

    # 2. Gemini 1.5 Flash 分析 (APIバージョンを v1 に、モデルを models/ を付けて指定)
    # キーが正しければ、この v1 URLが最も安定しています
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": f"以下のニュースを日本語で要約し、明日の米国株の予測を絵文字付きで楽しく教えて：\n{all_news}"}]}]
    }
    
    try:
        response = requests.post(url, json=payload)
        res_json = response.json()
        
        if "candidates" in res_json:
            report = res_json["candidates"][0]["content"]["parts"][0]["text"]
        elif "error" in res_json:
            # エラーの詳細をそのまま出す（ここでAPIキーの状態がわかります）
            report = f"AIエラー: {res_json['error'].get('message', '不明なエラー')}\n(APIキーの有効性を確認してください)"
        else:
            report = f"AI応答エラー: {res_json}"
            
    except Exception as e:
        report = f"システムエラー: {str(e)}"

    # 3. Discord送信
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
        webhook.execute()

if __name__ == "__main__":
    main()
