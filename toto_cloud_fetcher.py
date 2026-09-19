import json
import os
import re
import sys
import time
import requests

# GASのWebアプリURL
GAS_WEBAPP_URL = os.getenv("https://script.google.com/macros/s/AKfycbz8Q-fjHB9YCZCw-W0eRtrwb5R4R6XaOtk0e7U2WLZ9xKnb1AcPOnMTCGPu8VLtwqLg/exec", "")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
}

# 正しいドメイン (www.toto-dream.com)
TARGET_URLS = [
    "https://www.toto-dream.com/toto/index.html",
    "https://www.toto-dream.com/toto/",
]


def fetch_latest_round_and_carryover():
  env_round = os.getenv("TOTO_ROUND")
  if env_round:
    return env_round, 350000000

  for url in TARGET_URLS:
    try:
      res = requests.get(url, headers=HTTP_HEADERS, timeout=12)
      if res.status_code != 200:
        continue
      res.encoding = res.apparent_encoding or "Shift_JIS"
      html = res.text

      match = re.search(r"第\s*(\d{3,4})\s*回", html)
      if match:
        round_str = f"第{match.group(1)}回"
        co_match = re.search(r"キャリーオーバー[^\d]*([\d,]+)\s*円", html)
        carryover = int(co_match.group(1).replace(",", "")) if co_match else 0
        return round_str, carryover
    except Exception:
      continue
  return None, 0


def main():
  if not GAS_WEBAPP_URL:
    print("❌ エラー: GAS_WEBAPP_URL が設定されていません。")
    sys.exit(1)

  round_str, carryover = fetch_latest_round_and_carryover()
  if not round_str:
    print("❌ 開催回号を取得できませんでした（Fail-Safe安全停止）。")
    sys.exit(1)

  payload = {
      "round": round_str,
      "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
      "signal_id": f"SIG_{round_str}_{int(time.time())}",
      "carryover_amount": carryover,
      "toto_13matches": [
          {
              "match_no": i,
              "home_team": f"ホーム_{i}",
              "away_team": f"アウェイ_{i}",
              "public_votes": {"q1": 0.45, "q0": 0.28, "q2": 0.27},
              "prob": {"p1": 0.52, "p0": 0.25, "p2": 0.23},
          }
          for i in range(1, 14)
      ],
      "minitoto": {
          "frame": "A枠",
          "matches": [
              {
                  "match_no": i,
                  "home": f"チームA_{i}",
                  "away": f"チームB_{i}",
                  "q": {"q1": 0.4, "q0": 0.3, "q2": 0.3},
                  "p": {"p1": 0.5, "p0": 0.25, "p2": 0.25},
              }
              for i in range(1, 6)
          ],
      },
      "goal3_matches": [
          {
              "match_no": i,
              "home": f"チーム_{i}",
              "away": f"チーム_{i}",
              "q": [0.3, 0.3, 0.2, 0.2],
              "p": [0.4, 0.3, 0.2, 0.1],
          }
          for i in range(1, 4)
      ],
  }

  res = requests.post(
      GAS_WEBAPP_URL,
      data=json.dumps(payload),
      headers={"Content-Type": "application/json"},
      timeout=20,
  )
  print(f"📥 実行結果: {res.text}")


if __name__ == "__main__":
  main()
Step 3. 確定保存する
右上の Commit changes... をクリック。
出てきた画面で Commit changes（緑色のボタン） をもう一度クリックして保存します。
