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
# 2. 基本設定（ここで回号を直接変更することも可能です）
# ==============================================================================
DEFAULT_ROUND = "第1656回"  # ← Web取得できない場合のデフォルト保証値

GAS_WEBAPP_URL = os.getenv("GAS_WEBAPP_URL", "")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TARGET_URLS = [
    "https://www.toto-dream.com/toto/schedule/index.html",
    "https://www.toto-dream.com/toto/vote/toto/index.html",
    "https://www.toto-dream.com/toto/index.html",
]


# ==============================================================================
# 3. データ取得＆回号確定ロジック
# ==============================================================================
def fetch_toto_real_data():
  env_round = os.getenv("TOTO_ROUND")

  round_str = None
  if env_round and env_round.strip():
    round_str = env_round.strip()
    print(f"ℹ️ Secrets指定の回号を使用: {round_str}")

  matches_dict = {}
  carryover = 0

  for url in TARGET_URLS:
    try:
      print(f"📡 接続・解析中: {url}")
      res = requests.get(url, headers=HTTP_HEADERS, timeout=12)
      if res.status_code != 200:
        continue
      res.encoding = res.apparent_encoding or "Shift_JIS"
      html = res.text
      soup = BeautifulSoup(html, "html.parser")

      # 回号判定（HTML内の全4桁数字 1500〜1999 を網羅探索）
      if not round_str:
        all_nums = [int(n) for n in re.findall(r"(?:1[5-9]\d{2})", html)]
        if all_nums:
          max_num = max(all_nums)
          # 1654より大きい数字（最新回）が検出されたら採用
          if max_num > 1654:
            round_str = f"第{max_num}回"
            print(f"✅ Webから最新回号を自動検知: {round_str}")

      # キャリーオーバー額
      if carryover == 0:
        co_match = re.search(r"キャリーオーバー[^\d]*([\d,]+)\s*円", html)
        if co_match:
          carryover = int(co_match.group(1).replace(",", ""))

      # 対戦カード抽出
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
                matches_dict[m_no] = {"home": teams[0], "away": teams[1]}

      if len(matches_dict) >= 13:
        break
    except Exception as e:
      continue

  # 自動検知できなかった場合は DEFAULT_ROUND を強制適用
  if not round_str or round_str == "第1654回":
    round_str = DEFAULT_ROUND
    print(f"ℹ️ 保証デフォルト回号を適用: {round_str}")

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
    else:
      matches_data.append({
          "match_no": m_no,
          "home_team": f"対戦チーム_{m_no}_A",
          "away_team": f"対戦チーム_{m_no}_B",
          "public_votes": {"q1": 0.45, "q0": 0.28, "q2": 0.27},
          "prob": {"p1": 0.50, "p0": 0.25, "p2": 0.25},
      })

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
