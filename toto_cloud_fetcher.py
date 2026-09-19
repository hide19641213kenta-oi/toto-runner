import json
import os
import re
import subprocess
import sys
import time

# ==============================================================================
# 1. 必要なライブラリの自動セットアップ (bs4)
# ==============================================================================
try:
  from bs4 import BeautifulSoup
except ImportError:
  print("📦 解析ライブラリ (beautifulsoup4) を自動インストール中...")
  subprocess.check_call(
      [sys.executable, "-m", "pip", "install", "beautifulsoup4"]
  )
  from bs4 import BeautifulSoup

import requests

# ==============================================================================
# 2. 設定・定数宣言
# ==============================================================================
GAS_WEBAPP_URL = os.getenv("GAS_WEBAPP_URL", "")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TARGET_URLS = [
    "https://www.toto-dream.com/toto/index.html",
    "https://www.toto-dream.com/toto/",
]


# ==============================================================================
# 3. データ取得＆スクレイピングロジック
# ==============================================================================
def fetch_toto_real_data():
  env_round = os.getenv("TOTO_ROUND")

  html = ""
  selected_url = ""
  for url in TARGET_URLS:
    try:
      print(f"📡 公式サイトへ接続試行中: {url}")
      res = requests.get(url, headers=HTTP_HEADERS, timeout=15)
      if res.status_code == 200:
        res.encoding = res.apparent_encoding or "Shift_JIS"
        html = res.text
        selected_url = url
        break
    except Exception as e:
      print(f"⚠️ 接続警告 ({url}): {e}")

  if not html:
    print("❌ 公式サイトへの接続に失敗しました。")
    return None

  soup = BeautifulSoup(html, "html.parser")

  # --------------------------------------------------------------------------
  # A. 開催回号の特定（Secrets指定優先、無ければ最新数字を検索）
  # --------------------------------------------------------------------------
  round_str = None
  if env_round and env_round.strip():
    round_str = env_round.strip()
    print(f"ℹ️ Secrets指定の回号を使用: {round_str}")
  else:
    # ページ全体から「第XXXX回」の4桁数字を検索
    found_rounds = re.findall(r"第\s*(\d{4})\s*回", html)
    if found_rounds:
      nums = sorted(list(set([int(n) for n in found_rounds])), reverse=True)
      round_str = f"第{nums[0]}回"
      print(f"✅ 自動検知された最新回号: {round_str}")

  if not round_str:
    print("❌ 開催回号を取得できませんでした。")
    return None

  # --------------------------------------------------------------------------
  # B. キャリーオーバー額の抽出
  # --------------------------------------------------------------------------
  co_match = re.search(r"キャリーオーバー[^\d]*([\d,]+)\s*円", html)
  carryover = int(co_match.group(1).replace(",", "")) if co_match else 0
  print(f"💰 キャリーオーバー額: {carryover:,} 円")

  # --------------------------------------------------------------------------
  # C. DOM解析による対戦チーム名(13試合)抽出
  # --------------------------------------------------------------------------
  matches_dict = {}

  # テーブル要素を全探索
  for row in soup.find_all("tr"):
    cols = [
        col.get_text(strip=True)
        for col in row.find_all(["td", "th"])
        if col.get_text(strip=True)
    ]

    # 行内に試合番号（1〜13）が含まれるか検証
    for idx, text in enumerate(cols):
      if text.isdigit() and 1 <= int(text) <= 13:
        m_no = int(text)
        if m_no not in matches_dict:
          # 試合番号の直後にあるチーム名らしき文字列を取得
          teams = [
              c
              for c in cols[idx + 1 :]
              if not c.isdigit()
              and len(c) <= 10
              and "回" not in c
              and "指定" not in c
          ]
          if len(teams) >= 2:
            matches_dict[m_no] = {
                "home": teams[0],
                "away": teams[1],
            }

  matches_data = []
  for m_no in range(1, 14):
    if m_no in matches_dict:
      matches_data.append({
          "match_no": m_no,
          "home_team": matches_dict[m_no]["home"],
          "away_team": matches_dict[m_no]["away"],
          "public_votes": {"q1": 0.45, "q0": 0.28, "q2": 0.27},
          "prob": {"p1": 0.50, "p0": 0.25, "p2": 0.25},
      })

  print(f"📊 解析成功した対戦カード数: {len(matches_data)}/13 試合")

  # --------------------------------------------------------------------------
  # 🛡️ 事故防止安全ガード
  # --------------------------------------------------------------------------
  if len(matches_data) < 13:
    print(
        "\n⚠️ 事故防止ガード作動: Webサイトから13試合分すべてのチーム名を取得できませんでした。"
    )
    print(
        "💡 不完全なデータによる誤通知を防ぐため、安全に処理を自動停止しました。"
    )
    print(
        "👉 解決策: GitHubの Settings -> Secrets and variables -> Actions にて"
    )
    print("   Name: TOTO_ROUND / Secret: 第1656回 を設定してください。")
    return None

  return {
      "round": round_str,
      "carryover": carryover,
      "matches": matches_data,
  }


# ==============================================================================
# 4. メイン実行ブロック
# ==============================================================================
def main():
  print("=" * 65)
  print("🤖 toto Quant Engine - 実対戦データ収集・GAS伝送パイプライン")
  print("=" * 65)

  if not GAS_WEBAPP_URL:
    print("❌ エラー: GAS_WEBAPP_URL が設定されていません。")
    sys.exit(1)

  data = fetch_toto_real_data()

  if not data:
    print("\n🛑 事故防止安全装置により送信を停止しました。")
    sys.exit(1)

  # 送信データ構築
  payload = {
      "round": data["round"],
      "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
      "signal_id": f"SIG_{data['round']}_{int(time.time())}",
      "carryover_amount": data["carryover"],
      "toto_13matches": data["matches"],
      "minitoto": {
          "frame": "A枠",
          "matches": [
              {
                  "match_no": i,
                  "home": data["matches"][i - 1]["home_team"],
                  "away": data["matches"][i - 1]["away_team"],
                  "q": {"q1": 0.4, "q0": 0.3, "q2": 0.3},
                  "p": {"p1": 0.5, "p0": 0.25, "p2": 0.25},
              }
              for i in range(1, 6)
          ],
      },
      "goal3_matches": [
          {
              "match_no": i,
              "home": data["matches"][i - 1]["home_team"],
              "away": data["matches"][i - 1]["away_team"],
              "q": [0.3, 0.3, 0.2, 0.2],
              "p": [0.4, 0.3, 0.2, 0.1],
          }
          for i in range(1, 4)
      ],
  }

  print(f"🚀 GASへデータ伝送中... (対象: {data['round']})")
  res = requests.post(
      GAS_WEBAPP_URL,
      data=json.dumps(payload),
      headers={"Content-Type": "application/json"},
      timeout=20,
  )

  print(f"📥 実行結果: {res.text}")


if __name__ == "__main__":
  main()
