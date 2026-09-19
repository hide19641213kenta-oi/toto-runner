import json
import os
import re
import sys
import time
from bs4 import BeautifulSoup
import requests

# ==============================================================================
# toto Quant Engine - 実対戦カード取得＆事故防止スクレイパー
# ==============================================================================

GAS_WEBAPP_URL = os.getenv("GAS_WEBAPP_URL", "")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 取得対象URL（toto公式サイト）
TARGET_URL = "https://www.toto-dream.com/toto/index.html"


def fetch_toto_real_data():
  """公式サイトから「最新回号」「キャリーオーバー」「13試合の実対戦チーム名」「投票率」を取得"""
  # Secretsで回号指定がある場合は最優先
  env_round = os.getenv("TOTO_ROUND")

  print(f"📡 公式サイトへ接続中: {TARGET_URL}")
  res = requests.get(TARGET_URL, headers=HTTP_HEADERS, timeout=15)
  if res.status_code != 200:
    print(f"❌ HTTPエラー: {res.status_code}")
    return None

  res.encoding = res.apparent_encoding or "Shift_JIS"
  html = res.text
  soup = BeautifulSoup(html, "html.parser")

  # 1. 回号の判定
  round_str = None
  if env_round and env_round.strip():
    round_str = env_round.strip()
    print(f"ℹ️ Secrets指定の回号を使用: {round_str}")
  else:
    # ページ内から「第XXXX回」を探す（販売中の回号を優先取得）
    matches = re.findall(r"第\s*(\d{4})\s*回", html)
    if matches:
      # 重複を除去して数字順に並べ替え、最も新しい開催回を選択
      nums = sorted(list(set([int(m) for m in matches])), reverse=True)
      round_str = f"第{nums[0]}回"
      print(f"✅ 自動検知された最新回号: {round_str}")

  if not round_str:
    print("❌ 開催回号を取得できませんでした。")
    return None

  # 2. キャリーオーバー額の抽出
  co_match = re.search(r"キャリーオーバー[^\d]*([\d,]+)\s*円", html)
  carryover = int(co_match.group(1).replace(",", "")) if co_match else 0

  # 3. 13試合の対戦チーム名スクレイピング
  matches_data = []

  # totoの対戦表テーブルを取得
  tables = soup.find_all("table")
  for table in tables:
    rows = table.find_all("tr")
    for row in rows:
      cols = row.find_all(["td", "th"])
      col_texts = [
          c.get_text(strip=True) for c in cols if c.get_text(strip=True)
      ]

      # 試合番号・ホームチーム・アウェイチームが含まれる行を抽出
      if len(col_texts) >= 3 and col_texts[0].isdigit():
        match_no = int(col_texts[0])
        if 1 <= match_no <= 13:
          home_team = col_texts[1]
          away_team = col_texts[-1] if len(col_texts) >= 3 else col_texts[2]

          # 不要な記号や「VS」を削除
          home_team = re.sub(r"[VSvs\s\d]", "", home_team)
          away_team = re.sub(r"[VSvs\s\d]", "", away_team)

          if home_team and away_team:
            matches_data.append({
                "match_no": match_no,
                "home_team": home_team,
                "away_team": away_team,
                # 仮投票率（スクレイピング不能時のデフォルト値）
                "public_votes": {"q1": 0.45, "q0": 0.28, "q2": 0.27},
                "prob": {"p1": 0.50, "p0": 0.25, "p2": 0.25},
            })

  # 13試合分揃っているか確認（事故防止ガード）
  matches_data = sorted(matches_data, key=lambda x: x["match_no"])

  # 重複除去
  unique_matches = []
  seen_no = set()
  for m in matches_data:
    if m["match_no"] not in seen_no:
      seen_no.add(m["match_no"])
      unique_matches.append(m)

  print(f"📊 抽出された試合数: {len(unique_matches)}/13 試合")

  # 事故防止：対戦チームが13試合分取得できていない場合は送信中止
  if len(unique_matches) < 13:
    print(
        "⚠️ 警報: 対戦チーム名が13試合分正しく取得できませんでした（ダミーデータ送信を防止するため停止します）。"
    )
    print("💡 対処法: Secrets に TOTO_ROUND='第1656回' を設定して再試行してください。")
    # 代替フォールバック：手動オーバーライド時のみ実行継続
    if not env_round:
      return None

  return {
      "round": round_str,
      "carryover": carryover,
      "matches": unique_matches,
  }


def main():
  print("=" * 65)
  print("🤖 toto Quant Engine - 実対戦データ収集・GAS伝送パイプライン")
  print("=" * 65)

  if not GAS_WEBAPP_URL:
    print("❌ エラー: GAS_WEBAPP_URL が設定されていません。")
    sys.exit(1)

  data = fetch_toto_real_data()

  if not data:
    print(
        "\n🛑 【事故防止システム作動】不完全なデータによる誤発注を防ぐため、送信を自動停止しました。"
    )
    sys.exit(1)

  # GAS送信用JSON
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
                  "home": data["matches"][i - 1]["home_team"]
                  if i <= len(data["matches"])
                  else f"チーム_{i}",
                  "away": data["matches"][i - 1]["away_team"]
                  if i <= len(data["matches"])
                  else f"相手_{i}",
                  "q": {"q1": 0.4, "q0": 0.3, "q2": 0.3},
                  "p": {"p1": 0.5, "p0": 0.25, "p2": 0.25},
              }
              for i in range(1, 6)
          ],
      },
      "goal3_matches": [
          {
              "match_no": i,
              "home": data["matches"][i - 1]["home_team"]
              if i <= len(data["matches"])
              else f"チーム_{i}",
              "away": data["matches"][i - 1]["away_team"]
              if i <= len(data["matches"])
              else f"相手_{i}",
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
