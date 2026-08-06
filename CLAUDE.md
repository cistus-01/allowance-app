# kyuyocho（こどもの給与帳）

子どもの家事・成績・貯金を給料として管理する家族向け SaaS。Render でホスト中。

## Tech Stack
- Framework: Flask（Python）+ Jinja2 テンプレート
- Database: PostgreSQL（Neon）
- Hosting: Render.com（自動デプロイ）
- Container: Docker（ローカル開発 port 5000）

## Directory Structure
- `app/routes/` — Blueprint 群（auth, home, chores, grades, admin 等）
- `app/models.py` — SQLAlchemy ORM
- `app/database.py` — DB接続管理
- `app/static/` — CSS, JS, 画像
- `run.py` — アプリエントリポイント
- `render.yaml` — Render デプロイ設定

## Commands
- `pip install -r requirements.txt` — 依存関係
- `python run.py` — ローカル起動（port 5000）
- `gunicorn run:app` — 本番起動（render.yaml より）
- `docker compose up` — Docker 起動

## Environment Variables（Render ダッシュボードで管理）
- `DATABASE_URL` — PostgreSQL 接続文字列（Neon）
- `SECRET_KEY` — Flask セッションキー

## Deployment
- `git push` → Render が自動デプロイ（main ブランチ）
- ヘルスチェック: `GET /` → 200 OK
- DB マイグレーション: `render.yaml` の `startCommand` に含まれている

## Key Routes
- `/auth/login`, `/auth/register` — 認証
- `/chores/` — 家事管理（親は自分の分もチェック可能、子と割り勘計算）
- `/grades/` — 成績管理
- `/admin/payslip` — 給与明細（発行者を選択可能）
- `/admin/` — 管理者画面
- 現在すべて無料（有料プラン・Stripe決済は廃止）
