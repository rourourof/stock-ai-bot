import os
import requests
from discord_webhook import DiscordWebhook

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def main():
    # 利用可能なモデルの一覧を取得する
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    
    try:
        response = requests.get(url)
        res_json = response.json()
        
        if "models" in res_json:
            # generateContent に対応しているモデルだけを抽出
            available = []
            for m in res_json["models"]:
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    available.append(m["name"])
            
            report = "✅ 接続成功！利用可能なモデル一覧:\n" + "\n".join(available)
            report += "\n\nこの中にある名前を次のコードで使います。"
        else:
            report = f"❌ モデルリストの取得に失敗しました。内容: {res_json}"
            
    except Exception as e:
        report = f"⚠️ システムエラー: {str(e)}"

    # Discordに結果を送信
    if DISCORD_WEBHOOK_URL:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=report)
        webhook.execute()

if __name__ == "__main__":
    main()
