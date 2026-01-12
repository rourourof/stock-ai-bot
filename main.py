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
        result = newsapi.get_everything(q="US Stock Market", language='en', sort_by='relevancy', page_size=3)
        for article in result.get('articles', []):
            all_news += f"- {article['title']}\n"
    except:
        all_news = "ニュース取得制限中"

    # 2. Gemini AI 分析
    # ポイント：APIバージョンを v1beta にし、モデル名の前に models/ を明記します
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"以下の米国株ニュースを日本語で要約し、投資コメントを絵文字付きで作ってください：\n{all_news}"
            }]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()
        
        # 成功時の処理
        if "candidates" in res_json:
            report = res_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            # エラーの詳細をDiscordに送って原因を特定する
            error_info = res_json.get('error', {})
            report = f"AIエラー発生: {error_info.get('message', '不明なエラー')}\nコード: {error_info.get('code')}"
            
            # クォータ（429）エラー時のフォロー
            if error_info.get('code') == 429:
                report = "【制限エラー】APIの無料枠を使い切りました。1時間ほど待ってから実行してください。"
                
    except Exception as e:
        report = f"システムエラー: {str(e)}"

    # 3. Discordへの通知
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
        webhook.execute()

if __name__ == "__main__":
    main()
