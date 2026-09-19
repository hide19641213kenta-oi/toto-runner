import requests
import json
import os
import re

# ★環境変数または直接URLを設定
GAS_WEBAPP_URL = os.getenv("GAS_WEBAPP_URL", "https://script.google.com/macros/s/AKfycbz8Q-fjHB9YCZCw-W0eRtrwb5R4R6XaOtk0e7U2WLZ9xKnb1AcPOnMTCGPu8VLtwqLg/exec")

def fetch_and_send_toto_data():
    print("🤖 クラウドPythonデータ収集ロボット起動...")
    
    target_url = "https://www.toto-official.jp/toto/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"❌ Web取得失敗 (HTTPステータス: {response.status_code})。送信を安全に中止します。")
            return

        html_text = response.text
        
        # 開催回号の抽出
        round_match = re.search(r'第\s*(\d{4})\s*回', html_text)
        if not round_match:
            print("❌ 回号の抽出に失敗しました。誤送信を防ぐため処理を中止します。")
            return

        round_str = f"第{round_match.group(1)}回"
        
        # キャリーオーバー額の抽出
        co_match = re.search(r'キャリーオーバー[^\d]*([\d,]+)\s*円', html_text)
        carryover = int(co_match.group(1).replace(',', '')) if co_match else 0
        
        print(f"✅ データ取得成功: {round_str} | C/O: {carryover:,}円")
        
        # 本来はここでブックメーカーオッズやAIモデルから実データ（チーム名・勝率P・投票率Q）を組み立てます
        payload = {
            "round": round_str,
            "carryover_amount": carryover,
            "signal_id": f"SIG_{round_str}_{int(requests.compat.time.time())}",
            "toto_13matches": [
                # 実データの配列を格納
            ]
        }
        
        # 3. 正常にデータが揃った場合のみGASへ送信
        res = requests.post(GAS_WEBAPP_URL, json=payload)
        print("🚀 GASへデータ送信完了:", res.text)

    except Exception as e:
        print(f"❌ 通信・処理エラーが発生しました（送信中止）: {e}")

if __name__ == "__main__":
    fetch_and_send_toto_data()
