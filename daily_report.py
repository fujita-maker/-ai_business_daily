#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI自動事業開発 - 毎朝レポート生成スクリプト

毎朝cronから起動され、
  1. Claude APIにWeb検索させて「今日時点の」B2B AIエージェント/Micro-SaaS/
     デジタル商品自動販売の事業機会を調査・採点させる
  2. 結果を指定フォーマットのレポートに整形
  3. メール and/or Slackに配信する

このスクリプトは「発見と一次スクリーニングとレポート作成」のみを自動化します。
実際の顧客ヒアリング・販売テストの実行・予算の意思決定は人間が行う前提です
(README.md の「このスクリプトが自動化する範囲」を参照)。
"""

import os
import sys
import json
import smtplib
import datetime
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from dotenv import load_dotenv

try:
    import anthropic
except ImportError:
    print("anthropic パッケージが見つかりません。 pip install anthropic を実行してください。")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None  # Slack配信を使わないなら無くてもOK

# ---------------------------------------------------------------------------
# 設定読み込み
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")  # 最新モデル名は docs.claude.com で要確認

DELIVERY_METHOD = os.getenv("DELIVERY_METHOD", "email")  # "email" / "slack" / "both"

# メール設定
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
EMAIL_TO = os.getenv("EMAIL_TO")

# Slack設定
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
ARCHIVE_DIR = BASE_DIR / "archive"
ARCHIVE_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "daily_report.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# レポート生成の指示(システムプロンプト)
# ここが「毎日の事業会議」の中身。3本柱・採点基準・レポート形式を固定化している。
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
あなたはAI事業開発の専属リサーチャー件アナリストです。
以下の3本柱に絞って、今日時点の情報をWeb検索で調べ、指定フォーマットで日本語のレポートを作成してください。

【対象3本柱】
1. B2B AIエージェント(特に垂直特化・中小事業者向けの手薄なニッチ)
2. Micro-SaaS(ニッチ業務特化、月額課金、粗利率70%以上を狙えるもの)
3. デジタル商品の自動販売(テンプレート・プロンプト集・ノウハウ商品など、粗利率90%以上)

【絶対に守るルール】
- 検証不能なSNS投稿の売上自慢を事実として書かない。出典が曖昧な数字は「未検証」と明記する。
- 具体的な数字(想定月商・利益)は「保守的な推定」であることを必ず明記し、断定しない。
- 派手さより「支払い実績が既にあるか」「競合が少ないか」「日本でまだ手薄か」を重視する。
- 感情論・煽り文句を書かない。淡々と事実とリスクを書く。

【出力フォーマット】(このMarkdown構造を厳守すること)

# 本日のAI事業レポート(YYYY-MM-DD)

## 本日発見した事業機会 TOP10(3本柱に限定)
順位・事業名・タイプ(エージェント/SaaS/デジタル商品)・根拠(出典の要約)を表形式で。

## 日本でまだ流行っていないTOP3
海外で先行しており、日本市場でまだ手薄なものを3つ。理由付きで。

## 最も有望な1事業
事業名・理由・想定顧客・競合状況・想定粗利率・想定月利益(保守的レンジ、前提条件付き)

## 今日AIが調べた/整理したこと
実施した検索・整理内容を箇条書きで(検証プロセスの透明性のため)

## 今日、人間が判断すること(最大3項目)
実際の顧客ヒアリングや予算執行など、AIが代行できない意思決定のみ。

## 前回からの差分
新しく浮上した機会、または評価が下がった機会があれば触れる(初回はその旨を記載)。

必ず日本語で、簡潔かつ具体的に書いてください。前置きの挨拶や結びの言葉は不要です。
"""

USER_PROMPT = "本日分のAI事業機会レポートを作成してください。"


# ---------------------------------------------------------------------------
# Claude APIでレポート生成
# ---------------------------------------------------------------------------
def generate_report() -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY が設定されていません(.env を確認してください)")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    logger.info("Claude APIへレポート生成をリクエスト中...")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": USER_PROMPT}],
    )

    # レスポンスのcontentブロックからtextのみ抽出して結合
    text_parts = [block.text for block in response.content if block.type == "text"]
    report_text = "\n".join(text_parts).strip()

    if not report_text:
        raise RuntimeError("Claude APIからテキストが返りませんでした(レスポンス構造を確認してください)")

    logger.info("レポート生成完了(%d文字)", len(report_text))
    return report_text


# ---------------------------------------------------------------------------
# 配信
# ---------------------------------------------------------------------------
def send_email(report_text: str, today_str: str):
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_TO]):
        logger.warning("メール設定が不完全なため、メール送信をスキップしました")
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = f"【AI事業レポート】{today_str}"
    msg.attach(MIMEText(report_text, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

    logger.info("メール送信完了: %s", EMAIL_TO)


def send_slack(report_text: str):
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL が未設定のため、Slack送信をスキップしました")
        return
    if requests is None:
        logger.warning("requests パッケージが無いため、Slack送信をスキップしました")
        return

    # Slackの1メッセージ文字数制限(約40,000字)対策で分割
    chunks = [report_text[i:i + 3500] for i in range(0, len(report_text), 3500)]
    for chunk in chunks:
        resp = requests.post(SLACK_WEBHOOK_URL, json={"text": chunk}, timeout=15)
        resp.raise_for_status()

    logger.info("Slack送信完了")


def archive_report(report_text: str, today_str: str):
    path = ARCHIVE_DIR / f"{today_str}.md"
    path.write_text(report_text, encoding="utf-8")
    logger.info("レポートをアーカイブ: %s", path)


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------
def main():
    today_str = datetime.date.today().isoformat()
    logger.info("=== 毎朝レポート処理開始: %s ===", today_str)

    try:
        report_text = generate_report()
    except Exception as e:
        logger.exception("レポート生成に失敗しました: %s", e)
        # 失敗時も分かるように最低限の通知を試みる
        error_note = f"【エラー】{today_str} のレポート生成に失敗しました。\n詳細: {e}\nログを確認してください: {LOG_DIR / 'daily_report.log'}"
        if DELIVERY_METHOD in ("email", "both"):
            try:
                send_email(error_note, today_str)
            except Exception:
                logger.exception("エラー通知メールの送信にも失敗しました")
        if DELIVERY_METHOD in ("slack", "both"):
            try:
                send_slack(error_note)
            except Exception:
                logger.exception("エラー通知Slackの送信にも失敗しました")
        sys.exit(1)

    archive_report(report_text, today_str)

    if DELIVERY_METHOD in ("email", "both"):
        try:
            send_email(report_text, today_str)
        except Exception:
            logger.exception("メール送信に失敗しました")

    if DELIVERY_METHOD in ("slack", "both"):
        try:
            send_slack(report_text)
        except Exception:
            logger.exception("Slack送信に失敗しました")

    logger.info("=== 毎朝レポート処理完了: %s ===", today_str)


if __name__ == "__main__":
    main()
