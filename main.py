import os
import requests
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
        all_news = "ニュース取得に失敗しました。"

    # 2. 利用可能なモデルの自動判別
    # どのモデルが使えるのかリストを取得します
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    target_model = "models/gemini-1.5-flash" # デフォルト
    
    try:
        list_res = requests.get(list_url).json()
        if "models" in list_res:
            # gemini-1.5-flash または gemini-pro を探す
            models = [m["name"] for m in list_res["models"] if "generateContent" in m["supportedGenerationMethods"]]
            # 優先順位をつけてモデルを選択
            for candidate in ["models/gemini-1.5-flash", "models/gemini-1.5-flash-latest", "models/gemini-pro"]:
                if candidate in models:
                    target_model = candidate
                    break
            print(f"使用モデル決定: {target_model}")
        else:
            print("モデルリストが取得できません。デフォルトを使用します。")
    except:
        print("モデルリスト取得失敗。")

    # 3. 決定したモデルで Gemini AI 分析を実行
    gen_url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": f"以下の米国株ニュースを日本語で要約して：\n{all_news}"}]}]
    }
    
    try:
        response = requests.post(gen_url, json=payload)
        res_json = response.json()
        
        if "candidates" in res_json:
            report = res_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            error_msg = res_json.get('error', {}).get('message', '不明なエラー')
            # 使えるモデルを報告する
            report = f"AIエラー: {error_msg}\n使用を試みたモデル: {target_model}\n※APIキーがGemini用ではない可能性があります。"
            
    except Exception as e:
        report = f"システムエラー: {str(e)}"

    # 4. Discordへの通知
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
        webhook.execute()

if __name__ == "__main__":
    main()
