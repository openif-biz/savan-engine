# iina_app_test.py
import requests

# 実際に ngrok で立ち上げた URL に置き換えてください
NGROK_URL = "https://85203db8d816.ngrok-free.app"

def test_iina_connection():
    """Linode の app.py に JSON データを送信してレスポンスを確認"""
    data = {"task": "テスト課題"}
    try:
        response = requests.post(NGROK_URL, json=data, timeout=10)
        print("[IINA] レスポンス:", response.json())
    except Exception as e:
        print("[IINA] エラー:", e)

if __name__ == "__main__":
    print("[IINA] 接続テスト開始")
    test_iina_connection()
