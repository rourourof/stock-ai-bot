import os
import requests
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def main():
    # 1. ニュース取得
    news_content = ""
    try:
        newsapi = NewsApiClient(api_key=NEWS_API_KEY)
        result = newsapi.get_everything(q="US stock market", language='en', sort_by='relevancy', page_size=2)
        for article in result.get('articles', []):
            news_content += f"Title: {article['title']}\n"
    except:
        news_content = "News acquisition failed."

    # 2. OpenRouter (Gemini 2.0 Flash 無料版)
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/my-stock-ai", # OpenRouter用に適当なURLを指定
        "X-Title": "Stock Analysis Bot"
    }
    
    payload = {
        "model": "google/gemini-2.0-flash-exp:free", # 現在最も通りやすい無料モデル
        "messages": [
            {"role": "user", "content": f"以下のニュースを日本語で要約し、明日の米国株予測をして：\n{news_content}"}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        res_json = response.json()
        
        if "choices" in res_json:
            report = res_json["choices"][0]["message"]["content"]
        else:
            # エラー原因を詳しく表示
            report = f"AIエラー: {res_json.get('error', {}).get('message', '詳細不明')}\n※OpenRouterのSettings > Privacyで『Allow free models』をONにしましたか？"
    except Exception as e:
        report = f"システムエラー: {str(e)}"

    # 3. Discord送信
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
        webhook.execute()

if __name__ == "__main__":
    main()
