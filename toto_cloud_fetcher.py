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

# 対戦表が存在するページURL候補（順次探索）
TARGET_URLS = [
    "https://www.toto-dream.com/toto/schedule/index.html",
    "https://www.toto-dream.com/toto/vote/toto/index.html",
    "https://www.toto-dream.com/toto/index.html",
]


# ==============================================================================
# 3. データ取得＆多重探索スクレイピング
# ==============================================================================
def fetch_toto_real_data():
  env_round = os.getenv("TOTO_ROUND")

  round_str = env_round.strip() if (env_round and env_round.strip()) else None
  matches_dict = {}
  carryover = 0

  for url in TARGET_URLS:
    try:
      print(f"📡 ページ接続試行中: {url}")
      res = requests.get(url, headers=HTTP_HEADERS, timeout=15)
      if res.status_code != 200:
        continue
      res.encoding = res.apparent_encoding or "Shift_JIS"
      html = res.text
      soup = BeautifulSoup(html, "html.parser")

      # 回号自動検知（Secrets指定がない場合）
      if not round_str:
        found_rounds = re.findall(r"第\s*(\d{4})\s*回", html)
        if found_rounds:
          nums = sorted(list(set([int(n) for n in found_rounds])), reverse=True)
          round_str = f"第{nums[0]}回"

      # キャリーオーバー額抽出
      if carryover == 0:
        co_match = re.search(r"キャリーオーバー[^\d]*([\d,]+)\s*円", html)
        if co_match:
          carryover = int(co_match.group(1).replace(",", ""))

      # 対戦カード（13試合）解析
      for row in soup.find_all("tr"):
        cols = [
            col.get_text(strip=True)
            for col in row.find_all(["td", "th"])
            if col.get_text(strip=True)
        ]
        for idx, text in enumerate(cols):
          if text.isdigit() and 1 <= int(text) <= 13:
            m_no = int(text)
            if m_no not in matches_dict:
              teams = [
                  c
                  for c in cols[idx + 1 :]
                  if not c.isdigit()
                  and len(c) <= 10
                  and "回" not in c
                  and "指定" not in c
                  and "組" not in c
              ]
              if len(teams) >= 2:
                matches_dict[m_no] = {
                    "home": teams[0],
                    "away": teams[1],
                }

      if len(matches_dict) >= 13:
        print(f"✅ 13試合の対戦カード取得に成功しました ({url})")
        break
    except Exception as e:
      print(f"⚠️ 解析スルー ({url}): {e}")

  if not round_str:
    round_str = "第1656回"

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

  print(f"📊 最終抽出結果: 第{round_str} / {len(matches_data)}/13 試合")

  # 13試合未満の場合は、対戦カードを生成・事故防止チェック
  if len(matches_data) < 13:
    print(
        "\n⚠️ 対戦カードの完全自動抽出が一部制限されたため、フォールバックモードで全13試合を補正生成します。"
    )
    # 不足分を補完
    existing_nos = {m["match_no"] for m in matches_data}
    for m_no in range(1, 14):
      if m_no not in existing_nos:
        matches_data.append({
            "match_no": m_no,
            "home_team": f"対戦チーム_{m_no}_A",
            "away_team": f"対戦チーム_{m_no}_B",
            "public_votes": {"q1": 0.45, "q0": 0.28, "q2": 0.27},
            "prob": {"p1": 0.50, "p0": 0.25, "p2": 0.25},
        })
    matches_data = sorted(matches_data, key=lambda x: x["match_no"])

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
