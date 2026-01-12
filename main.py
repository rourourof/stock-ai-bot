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
    # 1. ニュースの取得（負荷を減らすため3件に限定）
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    all_news = ""
    try:
        # クエリを絞り、取得件数を3件にする
        result = newsapi.get_everything(q="US Stock Market", language='en', sort_by='relevancy', page_size=3)
        for article in result.get('articles', []):
            all_news += f"- {article['title']}\n"
    except:
        all_news = "ニュース取得制限中"

    # 2. Gemini 1.5 Flash を使用（2.0よりも無料枠が安定しています）
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"以下の米国株ニュースを日本語で3行程度に要約し、投資コメントを短く作成して：\n{all_news}"
            }]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()
        
        if "candidates" in res_json:
            report = res_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            # 429エラーが出た場合の日本語メッセージ
            error_msg = res_json.get('error', {}).get('message', '')
            if "429" in str(response.status_code):
                report = "【制限エラー】Gemini APIの無料枠の上限に達しました。10分〜1時間ほど時間を置いてから再度実行してください。"
            else:
                report = f"AIエラー: {error_msg}"
    except Exception as e:
        report = f"システムエラー: {str(e)}"

    # 3. Discordへの通知
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
        webhook.execute()

if __name__ == "__main__":
    main()
