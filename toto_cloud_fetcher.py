import json
import os
import re
import sys
import time
import requests

# ==============================================================================
# toto Quant Engine - 実対戦カード取得＆事故防止スクレイパー (標準ライブラリ版)
# ==============================================================================

GAS_WEBAPP_URL = os.getenv("GAS_WEBAPP_URL", "")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TARGET_URL = "https://www.toto-dream.com/toto/index.html"


def fetch_toto_real_data():
  env_round = os.getenv("TOTO_ROUND")

  print(f"📡 公式サイトへ接続中: {TARGET_URL}")
  try:
    res = requests.get(TARGET_URL, headers=HTTP_HEADERS, timeout=15)
    if res.status_code != 200:
      print(f"❌ HTTP通信エラー: Status {res.status_code}")
      return None
    res.encoding = res.apparent_encoding or "Shift_JIS"
    html = res.text
  except Exception as e:
    print(f"❌ 接続失敗: {e}")
    return None

  # 1. 回号の判定（Secrets指定があれば最優先、なければサイト内から最大数字を自動取得）
  round_str = None
  if env_round and env_round.strip():
    round_str = env_round.strip()
    print(f"ℹ️ Secrets指定の回号を使用: {round_str}")
  else:
    matches = re.findall(r"第\s*(\d{4})\s*回", html)
    if matches:
      nums = sorted(list(set([int(m) for m in matches])), reverse=True)
      round_str = f"第{nums[0]}回"
      print(f"✅ 自動検知された最新回号: {round_str}")

  if not round_str:
    print("❌ 開催回号を取得できませんでした。")
    return None

  # 2. キャリーオーバー額の抽出
  co_match = re.search(r"キャリーオーバー[^\d]*([\d,]+)\s*円", html)
  carryover = int(co_match.group(1).replace(",", "")) if co_match else 0

  # 3. HTMLから対戦チーム名をスキャン（標準ライブラリ解析）
  # スクリプト・スタイルタグを除去
  clean_html = re.sub(
      r"<(script|style)[^>]*>.*?</\1>",
      "",
      html,
      flags=re.DOTALL | re.IGNORECASE,
  )
  td_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)
  raw_tds = [
      re.sub(r"<[^>]+>", "", td).strip() for td in td_pattern.findall(clean_html)
  ]

  found_matches = {}
  for i in range(len(raw_tds) - 2):
    txt = raw_tds[i]
    if txt.isdigit() and 1 <= int(txt) <= 13:
      m_num = int(txt)
      if m_num not in found_matches:
        candidates = [
            t
            for t in raw_tds[i + 1 : i + 6]
            if t and not t.isdigit() and len(t) <= 12 and "回" not in t
        ]
        if len(candidates) >= 2:
          found_matches[m_num] = {
              "home": candidates[0],
              "away": candidates[1],
          }

  matches_data = []
  for m_no in range(1, 14):
    if m_no in found_matches:
      matches_data.append({
          "match_no": m_no,
          "home_team": found_matches[m_no]["home"],
          "away_team": found_matches[m_no]["away"],
          "public_votes": {"q1": 0.45, "q0": 0.28, "q2": 0.27},
          "prob": {"p1": 0.50, "p0": 0.25, "p2": 0.25},
      })

  print(f"📊 抽出成功した対戦カード数: {len(matches_data)}/13 試合")

  # 🛡️ 事故防止安全ガード：13試合分のチーム名が揃わない場合は絶対送信しない
  if len(matches_data) < 13:
    print(
        "\n⚠️ 事故防止ガード作動: 13試合分の対戦チーム名が不完全なため、誤発注防止のため送信を停止します。"
    )
    print("💡 【即時解決策】")
    print(
        "   GitHubの Settings -> Secrets and variables -> Actions にて"
    )
    print("   Name: TOTO_ROUND / Secret: 第1656回 を追加してください。")
    return None

  return {
      "round": round_str,
      "carryover": carryover,
      "matches": matches_data,
  }


def main():
  print("=" * 60)
  print("🤖 toto Quant Engine - 実対戦データ取得・事故防止パイプライン")
  print("=" * 60)

  if not GAS_WEBAPP_URL:
    print("❌ エラー: GAS_WEBAPP_URL が設定されていません。")
    sys.exit(1)

  data = fetch_toto_real_data()

  if not data:
    print("\n🛑 安全装置により処理を中断しました。")
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

  print(f"🚀 GASへデータを送信中... (対象: {data['round']})")
  res = requests.post(
      GAS_WEBAPP_URL,
      data=json.dumps(payload),
      headers={"Content-Type": "application/json"},
      timeout=20,
  )

  print(f"📥 実行結果: {res.text}")


if __name__ == "__main__":
  main()
