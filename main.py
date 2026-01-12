import os
import yfinance as yf
from newsapi import NewsApiClient
import google.generativeai as genai
from discord_webhook import DiscordWebhook

# APIキーの設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Geminiの初期化
genai.configure(api_key=GEMINI_API_KEY)

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

    # 2. Gemini AI による分析
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"以下の米国株ニュースを日本語で要約し、投資アドバイスを絵文字付きで作成して：\n{all_news}"
        response = model.generate_content(prompt)
        report = response.text
    except Exception as e:
        report = f"AI分析エラー: {str(e)}"

    # 3. Discordへの通知（送信失敗時にエラーを出すように変更）
    if not DISCORD_WEBHOOK_URL:
        print("エラー: DISCORD_WEBHOOK_URL が設定されていません。")
        return

    print(f"Discordに送信中... 内容: {report[:20]}...") # ログに一部表示
    
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
    response = webhook.execute()
    
    if response:
        print("Discordへの送信に成功しました！")
    else:
        print("Discordへの送信に失敗しました。Webhook URLが正しいか確認してください。")

if __name__ == "__main__":
    main()
