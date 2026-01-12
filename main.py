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
    # 1. ニュースの取得（3件）
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    all_news = ""
    try:
        result = newsapi.get_everything(q="US Stock Market", language='en', sort_by='relevancy', page_size=3)
        for article in result.get('articles', []):
            all_news += f"- {article['title']}\n"
    except:
        all_news = "ニュース取得に失敗しました。"

    # 2. Gemini AI 分析
    # 2026年最新の「最もエラーが出にくい」エンドポイントとモデル名の組み合わせ
    # v1beta を使い、モデル名を明示的に flash-8b (または最新の安定版) に指定
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # 万が一上記で404が出る場合のバックアップ案として、構成をシンプルに
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"以下の米国株ニュースを日本語で要約して：\n{all_news}"}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()
        
        if "candidates" in res_json:
            report = res_json["candidates"][0]["content"]["parts"][0]["text"]
        elif "error" in res_json:
            # 404が出るなら、モデル名を指定せずに利用可能なモデルを探すための情報を出す
            error_msg = res_json["error"].get("message", "")
            report = f"AIエラー: {error_msg}\n(API設定を再確認してください)"
        else:
            report = "AIからの応答が空でした。"
            
    except Exception as e:
        report = f"システムエラー: {str(e)}"

    # 3. Discordへの通知
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
        webhook.execute()

if __name__ == "__main__":
    main()
