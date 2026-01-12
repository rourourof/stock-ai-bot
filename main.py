import os
import requests
import datetime
import pytz
import yfinance as yf
import time
from newsapi import NewsApiClient

# === 設定 (GitHub Secretsから取得) ===
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY") 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

FREE_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-7b-instruct:free"
]

def send_to_discord(content):
    """ Discordへの送信を確実に行う関数 """
    if not DISCORD_WEBHOOK_URL:
        print("CRITICAL ERROR: DISCORD_WEBHOOK_URL is not set!")
        return
    try:
        payload = {"content": content}
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
        res.raise_for_status()
    except Exception as e:
        print(f"Discord Send Error: {e}")

def get_detailed_market_data():
    targets = {"NVDA": "NVIDIA", "^SOX": "半導体指数", "ES=F": "S&P500先物", "NQ=F": "ナスダック100先物"}
    report_data = ""
    for ticker, name in targets.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if len(hist) < 2: continue
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            report_data += f"{name}: {curr['Close']:.2f} ({change_pct:+.2f}%)\n"
        except: pass
    return report_data

def call_ai_with_retry(prompt):
    """ AIを順番に試し、エラー内容を蓄積する """
    errors = []
    for model_name in FREE_MODELS:
        try:
            print(f"Trying {model_name}...")
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/my-stock-ai"
                },
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.8
                },
                timeout=180
            )
            data = res.json()
            if 'choices' in data:
                return data['choices'][0]['message']['content'], model_name
            else:
                err_msg = data.get('error', {}).get('message', 'Unknown Error')
                errors.append(f"{model_name}: {err_msg}")
                time.sleep(5)
        except Exception as e:
            errors.append(f"{model_name} Exception: {str(e)}")
            continue
    return None, errors

def main():
    # 起動直後のシークレットチェック
    if not OPENROUTER_API_KEY or not DISCORD_WEBHOOK_URL:
        print(f"KEY MISSING: Gemini API Key: {'OK' if OPENROUTER_API_KEY else 'MISSING'}, Webhook: {'OK' if DISCORD_WEBHOOK_URL else 'MISSING'}")
        return

    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    is_morning = 5 <= now.hour <= 11
    
    market_info = get_detailed_market_data()
    
    prompt = f"現在は2026/01/12です。米国株ストラテジストとして、以下のデータに基づき4000文字以上の超詳細レポートを執筆せよ。絵文字多用。構成：1.ニュース格付け、2.NVDA個別分析、3.地政学AI分析、4.{'朝の答え合わせ' if is_morning else '今夜の予想'} \nデータ: {market_info}"

    report, error_log = call_ai_with_retry(prompt)

    if report:
        # 分割送信
        chunks = [report[i:i+1900] for i in range(0, len(report), 1900)]
        for chunk in chunks:
            send_to_discord(chunk)
            time.sleep(2)
    else:
        # 失敗した理由をDiscordに報告する
        error_report = "⚠️ AIレポート生成に失敗しました。原因:\n" + "\n".join(error_log)
        send_to_discord(error_report)

if __name__ == "__main__":
    main()
