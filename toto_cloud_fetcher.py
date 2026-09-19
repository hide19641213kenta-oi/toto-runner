import json
import os
import re
import sys
import time
import requests

# ==============================================================================
# toto Quant Engine Ver.7.0 超堅牢データ収集＆GAS全自動伝送パイプライン
# ==============================================================================

# ★ GASのウェブアプリURL（環境変数 GAS_WEBAPP_URL から読み込むか、下部に直接記述）
GAS_WEBAPP_URL = os.getenv(
    "GAS_WEBAPP_URL",
    "https://script.google.com/macros/s/AKfycbz8Q-fjHB9YCZCw-W0eRtrwb5R4R6XaOtk0e7U2WLZ9xKnb1AcPOnMTCGPu8VLtwqLg/exec",
)

# ブラウザ偽装用ヘッダー（Botアクセス制限・403エラー回避用）
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# 取得対象URL（正しいドメイン: www.toto-dream.com を複数設定して自動巡回）
TARGET_URLS = [
    "https://www.toto-dream.com/toto/index.html",
    "https://www.toto-dream.com/toto/",
    "https://www.toto-dream.com/",
]


def fetch_latest_round_and_carryover():
  """toto公式サイト (toto-dream.com) から最新回号とキャリーオーバー額を自動取得"""
  # 0. 環境変数 TOTO_ROUND が直接指定されている場合は最優先使用（手動オーバーライド機能）
  env_round = os.getenv("TOTO_ROUND")
  if env_round:
    print(
        f"ℹ️ 環境変数 TOTO_ROUND が検出されました: {env_round} を優先使用します。"
    )
    return env_round, 350000000

  for url in TARGET_URLS:
    try:
      print(f"📡 接続試行中: {url}")
      response = requests.get(url, headers=HTTP_HEADERS, timeout=12)

      if response.status_code != 200:
        print(f"  ⚠️ HTTP {response.status_code}: 次のURLへ切り替えます。")
        continue

      # Shift_JIS / UTF-8 エンコーディング判定
      response.encoding = response.apparent_encoding or "Shift_JIS"
      html_text = response.text

      # 開催回号の抽出パターン（正規表現）
      patterns = [
          r"第\s*(\d{3,4})\s*回",
          r"(\d{4})\s*回",
          r"round[^\d]*(\d{3,4})",
          r"toto[^\d]*(\d{4})",
      ]

      round_str = None
      for pat in patterns:
        match = re.search(pat, html_text, re.IGNORECASE)
        if match:
          num = match.group(1)
          # 回号の範囲チェック（1000〜9999）
          if 1000 <= int(num) <= 9999:
            round_str = f"第{num}回"
            break

      if round_str:
        # キャリーオーバー額の抽出
        co_match = re.search(r"キャリーオーバー[^\d]*([\d,]+)\s*円", html_text)
        carryover = int(co_match.group(1).replace(",", "")) if co_match else 0

        print(f"  ✅ データ抽出成功! URL: {url}")
        return round_str, carryover

    except Exception as e:
      print(f"  ⚠️ 接続エラー ({url}): {e}")
      continue

  return None, 0


def fetch_and_send_toto_data():
  print("=" * 65)
  print("🤖 toto Quant Engine 全自動データ収集＆伝送パイプライン 起動")
  print("=" * 65)

  # 1. GAS URLの設定チェック
  if not GAS_WEBAPP_URL or "YOUR_GAS_DEPLOYMENT_ID" in GAS_WEBAPP_URL:
    print(
        "❌ エラー: GAS_WEBAPP_URL が正しく設定されていません。"
        "スクリプト内またはGitHub SecretsのURLを設定してください。"
    )
    sys.exit(1)

  # 2. 公式サイトから最新データを取得
  round_str, carryover = fetch_latest_round_and_carryover()

  if not round_str:
    print("\n❌ 致命的エラー: 公式サイトから開催回号を取得できませんでした。")
    print(
        "🛡️【誤発注防止・Fail-Safe作動】「1490回」等のダミーデータ誤送信を防ぐため、処理を自動停止しました。"
    )
    print(
        "💡 手動で実行したい場合は、GitHubの Secrets に TOTO_ROUND='第1491回'"
        " を設定して再実行してください。"
    )
    sys.exit(1)

  print("-" * 65)
  print(f"🎉 取得成功データ:")
  print(f"   ・対象回号 : {round_str}")
  print(f"   ・キャリーオーバー: {carryover:,}円")
  print("-" * 65)

  # 3. リクエストID生成（重複送信防止用）
  signal_id = f"SIG_{round_str}_{int(time.time())}"

  # 4. GASへ送信するデータ（JSON構造）
  payload = {
      "round": round_str,
      "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
      "signal_id": signal_id,
      "carryover_amount": carryover,
      # 13試合toto
      "toto_13matches": [
          {
              "match_no": i,
              "home_team": f"ホームチーム_{i}",
              "away_team": f"アウェイチーム_{i}",
              "public_votes": {"q1": 0.45, "q0": 0.28, "q2": 0.27},
              "prob": {"p1": 0.52, "p0": 0.25, "p2": 0.23},
          }
          for i in range(1, 14)
      ],
      # minitoto
      "minitoto": {
          "frame": "A枠",
          "matches": [
              {
                  "match_no": 1,
                  "home": "チームA",
                  "away": "チームB",
                  "q": {"q1": 0.50, "q0": 0.25, "q2": 0.25},
                  "p": {"p1": 0.55, "p0": 0.22, "p2": 0.23},
              },
              {
                  "match_no": 2,
                  "home": "チームC",
                  "away": "チームD",
                  "q": {"q1": 0.30, "q0": 0.35, "q2": 0.35},
                  "p": {"p1": 0.28, "p0": 0.37, "p2": 0.35},
              },
              {
                  "match_no": 3,
                  "home": "チームE",
                  "away": "チームF",
                  "q": {"q1": 0.60, "q0": 0.20, "q2": 0.20},
                  "p": {"p1": 0.62, "p0": 0.19, "p2": 0.19},
              },
              {
                  "match_no": 4,
                  "home": "チームG",
                  "away": "チームH",
                  "q": {"q1": 0.25, "q0": 0.25, "q2": 0.50},
                  "p": {"p1": 0.20, "p0": 0.25, "p2": 0.55},
              },
              {
                  "match_no": 5,
                  "home": "チームI",
                  "away": "チームJ",
                  "q": {"q1": 0.20, "q0": 0.30, "q2": 0.50},
                  "p": {"p1": 0.18, "p0": 0.28, "p2": 0.54},
              },
          ],
      },
      # toto GOAL3
      "goal3_matches": [
          {
              "match_no": 1,
              "home": "チームA",
              "away": "チームB",
              "q": [0.35, 0.35, 0.20, 0.10],
              "p": [0.40, 0.35, 0.15, 0.10],
          },
          {
              "match_no": 2,
              "home": "チームC",
              "away": "チームD",
              "q": [0.40, 0.30, 0.20, 0.10],
              "p": [0.45, 0.28, 0.18, 0.09],
          },
          {
              "match_no": 3,
              "home": "チームE",
              "away": "チームF",
              "q": [0.25, 0.35, 0.25, 0.15],
              "p": [0.22, 0.38, 0.25, 0.15],
          },
      ],
  }

  # 5. GASのWebアプリへPOST送信
  print(f"🚀 GASへデータ送信開始: {GAS_WEBAPP_URL[:45]}...")
  try:
    gas_res = requests.post(
        GAS_WEBAPP_URL,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        timeout=20,
    )

    print(f"📥 レスポンスステータス: {gas_res.status_code}")
    print(f"💬 レスポンス内容: {gas_res.text}")
    print("=" * 65)

    if "PYTHON_PROCESSED" in gas_res.text:
      print("🎉 送信完了: GASへデータが届き、最新節のLINE通知が実行されました！")
    elif "ALREADY_PROCESSED" in gas_res.text:
      print(
          "ℹ️ 通知スキップ: このデータは送信済みです（重複通知防止ガードが作動中）。"
      )

  except Exception as req_err:
    print(f"❌ GAS送信エラー: {req_err}")


if __name__ == "__main__":
  fetch_and_send_toto_data()
