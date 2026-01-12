import os
import requests
import yfinance as yf
from newsapi import NewsApiClient
from discord_webhook import DiscordWebhook

# APIキーの設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def main():
    # 1. ニュースの取得
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    all_news = ""
    try:
        result = newsapi.get_everything(q="US Stock Market news", language='en', sort_by='relevancy', page_size=5)
        for article in result.get('articles', []):
            all_news += f"- {article['title']}\n"
    except:
        all_news = "ニュース取得に失敗しました。"

    # 2. Gemini 2.0 Flash を直接叩く (v1安定版URLを使用)
    # 404エラーの原因である v1beta を避け、確実に存在する v1 エンドポイントを叩きます
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"以下の米国株ニュースを日本語で要約し、投資コメントを絵文字付きで作ってください。：\n{all_news}"
            }]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()
        
        if "candidates" in res_json:
            report = res_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            # エラー内容を詳しく表示（デバッグ用）
            report = f"AIエラー: {res_json.get('error', {}).get('message', '不明なエラー')}\nコード: {res_json.get('error', {}).get('code', 'なし')}"
    except Exception as e:
        report = f"システムエラー: {str(e)}"

    # 3. Discordへの通知
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
        webhook.execute()

if __name__ == "__main__":
    main()
