import os
import requests
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# 名前はそのままでOK（中身を OpenRouter の sk-or-... に入れ替える）
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def main():
    # 1. ニュースの取得（最新ニュースを2件）
    news_content = ""
    try:
        newsapi = NewsApiClient(api_key=NEWS_API_KEY)
        result = newsapi.get_everything(q="US stock market", language='en', sort_by='relevancy', page_size=2)
        for article in result.get('articles', []):
            news_content += f"Title: {article['title']}\n"
    except:
        news_content = "ニュース取得に失敗しました。"

    # 2. OpenRouter 経由で無料AIを使用
    # モデル名「google/gemini-flash-1.5-8b:free」は完全に無料です
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "google/gemini-flash-1.5-8b:free",
        "messages": [
            {
                "role": "user", 
                "content": f"以下のニュースを日本語で3行程度に要約し、明日の米国株予測を絵文字付きで作成して：\n{news_content}"
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        res_json = response.json()
        
        if "choices" in res_json:
            report = res_json["choices"][0]["message"]["content"]
        else:
            report = f"AIエラー: {res_json.get('error', {}).get('message', '詳細不明')}"
    except Exception as e:
        report = f"システムエラー: {str(e)}"

    # 3. Discordへ送信
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
        webhook.execute()

if __name__ == "__main__":
    main()
