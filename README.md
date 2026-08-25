# AI事業機会 毎朝9時レポート ─ セットアップ手順

## これが自動化する範囲・しない範囲

**自動化される部分:**
- B2B AIエージェント/Micro-SaaS/デジタル商品自動販売の3本柱に絞ったWeb調査
- TOP10発見・日本未浸透TOP3・想定利益・今日の推奨アクションのレポート生成
- メールまたはSlackへの自動配信
- 過去レポートのアーカイブ保存(`archive/` フォルダ、日付ごとのMarkdownファイル)

**自動化されない(人間が必要な)部分:**
- 見込み客への実際のヒアリング・営業連絡
- 広告予算の実行(クレジットカード決済など)
- 「この事業を選ぶ」という最終意思決定

これはシステムの欠陥ではなく、意図的な設計です。ここまでAIに任せると、実売テストなしに資金が動いてしまいます。

---

## セットアップ手順(2種類:自前サーバー / GitHub→Render)

以下2通りの方法を用意しています。**PCのスリープ問題を避けたいなら、B)のRenderを推奨します。**

- A) 自分のPC/VPSで `crontab` を使う方法(下記「A. 自前サーバー版」)
- B) GitHubにpushして、Renderの「Cron Job」サービスで動かす方法(下記「B. GitHub→Render版」)

---

## A. 自前サーバー版

### 1. 動作環境の確認

Python 3.9以上が入っているPC、またはVPS/クラウドサーバー(常時起動しているマシン)が必要です。**あなたのノートPCで運用する場合、9時にPCがスリープ状態だとcronは動きません。** 確実に毎朝実行したいなら、以下のいずれかを推奨します:

- 常時起動しているデスクトップPC/自宅サーバー
- 月数百円〜で借りられる小型VPS(さくらのVPS、ConoHa VPS、AWS Lightsail等)

### 2. ファイル一式を配置

このやり取りで生成した以下のファイルを、実行したいマシンの同じフォルダにコピーしてください。

```
ai_business_daily/
├── daily_report.py     ← 本体
├── run_daily.sh         ← cron起動用ラッパー
├── requirements.txt
├── .env.example
└── README.md            ← このファイル
```

### 3. 依存パッケージのインストール

```bash
cd ai_business_daily
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

(venvを使う場合は `run_daily.sh` 内の `PYTHON_BIN="python3"` を `PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"` に変更してください)

### 4. APIキーと配信先を設定

```bash
cp .env.example .env
nano .env   # または好きなエディタで編集
```

最低限、以下を埋めてください:
- `ANTHROPIC_API_KEY` ─ https://console.anthropic.com で発行
- `DELIVERY_METHOD` ─ `email` か `slack` か `both`
- メールで受け取るなら `SMTP_*` と `EMAIL_TO`
- Slackで受け取るなら `SLACK_WEBHOOK_URL`

**Gmailを使う場合の注意:** 通常のログインパスワードではSMTP認証が通りません。Googleアカウントの「アプリパスワード」を発行して `SMTP_PASSWORD` に入れてください。

### 5. 手動で1回テスト実行

```bash
python3 daily_report.py
```

`logs/daily_report.log` にログが出ます。メール/Slackが届けば成功です。エラーが出た場合もログにエラー通知が届くように作っています。

### 6. 毎朝9時のcron登録

```bash
crontab -e
```

以下の1行を追加(パスは実際の配置場所に置き換えてください):

```
0 9 * * * /home/youruser/ai_business_daily/run_daily.sh
```

保存して終了すれば設定完了です。翌朝9時に自動実行されます。

### 7. 動作確認方法

- `archive/2026-08-26.md` のような日付ファイルが毎朝増えていればOK
- `logs/cron_stdout.log` にcronの実行ログが残ります
- 数日様子を見て、レポートの精度・切り口が期待と違えば `daily_report.py` 内の `SYSTEM_PROMPT` を調整してください(ここが「毎日の事業会議の議題」そのものです)

---

## B. GitHub→Render版(推奨:PCのスリープ問題を避けたい場合)

RenderはGitHubリポジトリと連携して、決まった時刻にコンテナを起動→スクリプト実行→終了、を自動でやってくれるサービスです。**注意:Renderのcronジョブは実行のたびにコンテナが使い捨てられるため、`archive/`フォルダへの保存は次回実行時に消えます。** 過去分の記録が必要な場合はメール/Slackの受信箱を実質的なアーカイブとして使うか、後日GitHubへの自動コミットなど別の仕組みを追加してください。

### 1. GitHubリポジトリを作る

このフォルダ一式(`daily_report.py`, `run_daily.sh`, `requirements.txt`, `.gitignore`, `README.md`)をGitHubの新規リポジトリにpushします。**`.env`ファイルは`.gitignore`で除外されているので、絶対にコミットしないでください**(APIキーが漏洩します)。

```bash
cd ai_business_daily
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/あなたのユーザー名/ai_business_daily.git
git push -u origin main
```

### 2. Renderでアカウント作成・GitHub連携

1. https://render.com でアカウント作成し、GitHubアカウントと連携
2. ダッシュボードで「New +」→「Cron Job」を選択
3. 先ほどpushしたリポジトリを選択

### 3. ビルド・実行コマンドを設定

| 項目 | 設定値 |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Command(実行コマンド) | `python daily_report.py` |
| Schedule(cron式) | `0 0 * * *` |

**重要:** Renderのcron式は**UTC(協定世界時)基準**です。日本時間9:00に実行したい場合、UTCでは0:00になるため `0 0 * * *` を指定してください(`0 9 * * *`ではありません)。夏時間の概念は日本にはないので、この対応は年間を通じて固定でOKです。

### 4. 環境変数(APIキー等)をRenderダッシュボードで設定

`.env`ファイルはコミットしていないので、代わりにRenderの管理画面の「Environment」タブから直接、以下を1つずつ登録します(`.env.example`と同じキー名):

- `ANTHROPIC_API_KEY`
- `CLAUDE_MODEL`
- `DELIVERY_METHOD`
- メール利用時: `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `EMAIL_FROM` `EMAIL_TO`
- Slack利用時: `SLACK_WEBHOOK_URL`

コード側は `os.getenv()` で環境変数を読んでいるので、`.env`ファイルの有無に関わらずRenderが注入した環境変数をそのまま使えます(修正不要です)。

### 5. デプロイして手動テスト

設定を保存すると自動でビルドが始まります。ダッシュボードの「Trigger Run」ボタンで即座に1回実行し、メール/Slackが届くか確認してください。

### 6. 以後の運用

- コードを直したら `git push` するだけで、次回実行分から自動反映されます
- 実行ログはRenderダッシュボードの「Logs」タブで確認できます
- 課金は実行時間に応じた従量制で、cronジョブは1サービスあたり月$1程度が下限の目安です(最新の料金は https://render.com/pricing で要確認)

---

## よくある詰まりどころ

| 症状 | 原因の可能性 |
|---|---|
| cronの時刻になっても何も起きない(自前サーバー版) | PCがスリープしていた/crontabの登録ミス。`crontab -l` で登録内容を確認 |
| Renderで9時ではなく変な時刻に実行される | UTC変換ミス。日本時間9:00は`0 0 * * *`(UTC 0:00) |
| Renderで毎回`archive/`が空になる | 仕様通り(ディスクが使い捨て)。過去分はメール/Slackの受信箱を確認 |
| メールが届かない | Gmailのアプリパスワード未設定、迷惑メールフォルダ |
| Slackに届かない | Webhook URLの期限切れ・チャンネル削除 |
| レポートの中身が薄い/的外れ | `SYSTEM_PROMPT` を具体化する(例:自分の業界知識・除外したいジャンルを追記) |
| APIコストが気になる | 1日1回・数千トークン程度なので通常は小額。心配なら https://console.anthropic.com の使用量ダッシュボードで確認 |

---

## 次のステップの提案

このレポートが安定して届くようになったら、次は「④小さく販売テスト」の一次連絡文(見込み客への最初のメッセージ)もテンプレート化し、レポートの「今日、人間が判断すること」に紐づけて出す形に拡張すると、STEP2〜4がさらに一気通貫になります。
