# こどもの給与帳 — アプリ仕様書

> 作成日: 2026-04-24  
> 対象: Jarvis（次回セッション以降の引き継ぎ用）

---

## 1. アプリ概要・哲学

**アプリ名:** こどもの給与帳  
**URL:** https://allowance-app-98k3.onrender.com  
**ターゲット:** 小学生とその保護者  
**料金:** 月額¥480（ファミリープラン、人数無制限）、30日間無料トライアル  

### 設計思想
- 「お小遣い」ではなく「給与」というフレームで子供に渡す
- 家事 = 自分の責任として毎日こなすもの（報酬は労力に応じた対価）
- 勉強 = 将来への投資（成績が学業給として翌学期以降の給与に反映）
- テスト満点ボーナス = 特別な努力への報酬（学年給と同単価）
- お金の流れを可視化することで金銭感覚を育てる

### 語彙ルール（アプリ内）
- お小遣い → **給料・給与**
- 稼ぐ → **家事報酬**
- 成績ボーナス → **学業給**
- 習い事の通知表評価 → **成績（◎〇△）**

### LP（ランディングページ）について
- SEO目的で `lp.html` のtitle・meta・h1は「おこづかい」キーワードを維持
- 比較表・フッター・JSON-LDは「こどもの給与帳」に統一済み
- **LP の SEO 用テキストは絶対に変更しないこと**

---

## 2. 技術スタック・インフラ

| 項目 | 内容 |
|------|------|
| フレームワーク | Flask（Python） |
| DB | SQLite（`/data/allowance.db`） |
| 認証 | Flask-Login |
| フロントエンド | Bootstrap 5.3 + Bootstrap Icons |
| 決済 | Stripe |
| デプロイ | Render（Web Service） |
| ローカル開発 | Docker（コンテナ名: `allowance-app`、ポート5000） |
| コード管理 | GitHub → Renderが自動デプロイ |

### ローカル反映手順
```bash
# ファイルをコンテナにコピー
docker cp app/routes/xxxx.py allowance-app:/app/app/routes/xxxx.py
docker cp app/templates/xxx/xxx.html allowance-app:/app/app/templates/xxx/xxx.html

# 再起動
docker restart allowance-app
```

### 本番デプロイ手順
```bash
cd /home/irodori/products/allowance-app
git add .
git commit -m "メッセージ"
git push origin main  # → Render が自動ビルド・デプロイ
```

---

## 3. ディレクトリ構成

```
allowance-app/
├── app/
│   ├── __init__.py          # Flaskアプリ生成・Blueprint登録
│   ├── database.py          # DB接続・init_db()・テーブル作成
│   ├── schema.sql           # CREATE TABLE 定義
│   ├── models.py            # User クラス（Flask-Login用）
│   ├── salary.py            # 給与計算ロジック（最重要）
│   ├── utils.py             # 共通ユーティリティ・デコレータ
│   ├── routes/
│   │   ├── auth.py          # ログイン・ログアウト・パスワードリセット
│   │   ├── home.py          # ホーム画面（LP・親・子供で分岐）
│   │   ├── chores.py        # 家事カレンダー・チェック
│   │   ├── grades.py        # 成績入力・確認
│   │   ├── finance.py       # 収支表
│   │   ├── goals.py         # ほしいものリスト
│   │   ├── admin.py         # 設定（子供管理・単価・プリセット・ボーナス・明細）
│   │   ├── stats.py         # 実績・積み上げ
│   │   ├── billing.py       # Stripe課金
│   │   ├── register.py      # 新規登録
│   │   ├── onboarding.py    # 登録後の初期設定ウィザード
│   │   ├── seo.py           # sitemap.xml等
│   │   ├── jarvis.py        # Jarvis用内部API（/jarvis/stats等）
│   │   └── setup.py         # デモデータ投入・DBパッチ
│   └── templates/
│       ├── base.html        # 共通レイアウト（ナビ・ボトムナビ）
│       ├── home/lp.html     # LP（未ログイン時のトップ）
│       ├── home/index_parent.html
│       ├── home/index_child.html
│       ├── auth/            # login・forgot・reset
│       ├── register/        # 新規登録
│       ├── chores/          # 家事カレンダー
│       ├── grades/          # 成績表
│       ├── finance/         # 収支表・日別詳細
│       ├── goals/           # ほしいものリスト
│       ├── admin/           # 設定・給料明細・ボーナス・夏休みボーナス・単価表
│       ├── stats/           # 実績・積み上げ
│       └── billing/         # プラン・課金
```

---

## 4. データベーススキーマ

### users
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| name | TEXT | 表示名 |
| username | TEXT UNIQUE | ログインID |
| email | TEXT | 親のみ。パスワードリセット用 |
| password_hash | TEXT | Werkzeug bcrypt |
| role | TEXT | 'parent' or 'child' |
| grade | INTEGER | 子供の学年（1〜6）。親はNULL |
| family_id | INTEGER | familiesテーブルのID |
| created_at | DATETIME | |

### families（課金単位）
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| name | TEXT | 家族名 |
| owner_user_id | INTEGER | 親のuser_id |
| stripe_customer_id | TEXT | |
| stripe_subscription_id | TEXT | |
| subscription_status | TEXT | 'trial' / 'active' / 'canceled' |
| trial_ends_at | DATETIME | |
| plan_ends_at | DATETIME | |

### chore_types（家事定義）
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| name | TEXT UNIQUE | 家事名 |
| unit_price | INTEGER | 単価（円）。複数人でやった場合は割り算 |
| is_active | BOOLEAN | 0=論理削除 |
| sort_order | INTEGER | 表示順 |

### chore_records（家事チェック記録）
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| user_id | INTEGER | 誰がやったか |
| chore_type_id | INTEGER | 何をやったか |
| record_date | DATE | いつやったか |
| checked_by | INTEGER | 誰が入力したか（親 or 本人） |
| UNIQUE(user_id, chore_type_id, record_date) | | 1日1回まで |

### subjects（教科）
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| name | TEXT UNIQUE | |
| is_active | BOOLEAN | |
| sort_order | INTEGER | |

デフォルト9教科: 国語・算数・理科・社会・英語・音楽・体育・図工・道徳

### grade_records（成績記録）
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| user_id | INTEGER | |
| subject_id | INTEGER | |
| year | INTEGER | 年度 |
| term | INTEGER | 1・2・3学期 |
| eval_1 | TEXT | ◎ / 〇 / △ / NULL（評価項目1） |
| eval_2 | TEXT | ◎ / 〇 / △ / NULL（評価項目2） |
| eval_3 | TEXT | ◎ / 〇 / △ / NULL（評価項目3） |
| UNIQUE(user_id, subject_id, year, term) | | |

各教科に評価項目が3つあることを前提とした設計（eval_1〜3）。

### finance_records（収支記録）
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| user_id | INTEGER | |
| record_date | DATE | |
| type | TEXT | 'income' / 'expense' |
| category | TEXT | 給料・テストボーナス・夏休みボーナス・お年玉 等 |
| item | TEXT | テストボーナス時は科目名 |
| amount | INTEGER | 円 |
| note | TEXT | |
| created_by | INTEGER | 入力者のuser_id |

**categoryの予約値:**
- `test_bonus` — テスト満点ボーナス（`/admin/bonus`から入力）
- `summer_bonus` — 夏休みボーナス（`/admin/summer_slip`から入力）
- それ以外は自由文字列（ユーザーが直接入力）

### pay_rates（単価設定）
| key | label | デフォルト値 |
|-----|-------|------------|
| base_pay | 基本給 | ¥100 |
| grade_pay_multiplier | 学年給（学年×） | ¥50 |
| eval_excellent | 成績給◎ | ¥50 |
| eval_good | 成績給〇 | ¥15 |
| eval_poor | 成績給△ | ¥0 |

> **注意:** DB初期値は`eval_excellent=150, eval_good=20`のままになっている場合あり。  
> 「デフォルトに戻す」ボタンを押すと上記の正しいデフォルト値に更新される。

### config_presets（設定プリセット）
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| family_id | INTEGER | |
| slot | INTEGER | 1・2・3のいずれか |
| label | TEXT | プリセット名 |
| pay_rates_json | TEXT | JSON文字列 |
| subjects_json | TEXT | JSON文字列 |
| chore_types_json | TEXT | JSON文字列 |
| saved_at | DATETIME | |
| UNIQUE(family_id, slot) | | |

### password_reset_tokens
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| user_id | INTEGER | |
| token | TEXT UNIQUE | ランダムトークン |
| expires_at | DATETIME | |
| used_at | DATETIME | NULL=未使用 |

### goals（ほしいものリスト）
| カラム | 型 | 備考 |
|--------|----|------|
| id | INTEGER PK | |
| user_id | INTEGER | |
| name | TEXT | 商品名 |
| target_amount | INTEGER | 目標金額 |
| emoji | TEXT | デフォルト🎯 |
| is_achieved | BOOLEAN | |
| achieved_at | DATETIME | |

---

## 5. 給与計算ロジック（salary.py）

### 基本構造
`calc_monthly_salary(user_id, year, month)` → 辞書を返す

```python
{
  'base_pay':     int,   # 固定基本給
  'grade_pay':    int,   # 学年給（学年 × grade_pay_multiplier）
  'academic_pay': int,   # 成績給（前学期の◎〇△から算出）
  'chore_pay':    int,   # 家事報酬（前月の家事記録から算出）
  'bonus_pay':    int,   # テストボーナス（前月記録分）
  'bonus_cnt':    int,   # ボーナス科目数
  'bonus_subjects': list,
  'total':        int,   # 合計
}
```

### タイミングのルール（最重要）

| 項目 | 参照タイミング |
|------|--------------|
| 基本給 | 固定（毎月） |
| 学年給 | 固定（毎月・学年ベース） |
| 成績給 | **前学期**の成績を参照 |
| 家事報酬 | **前月**の家事記録を参照 |
| テストボーナス | **前月**に記録されたものを参照 |

例: 2026年5月の給料 =
- 家事報酬: 2026年4月の家事記録
- 成績給: 2026年4月は1学期 → 前学期 = 2025年3学期の成績
- テストボーナス: 2026年4月に記録されたもの

### 学期の定義（month_to_term）
- 1〜3月 → 3学期（前年度扱い）
- 4〜7月 → 1学期
- 8〜12月 → 2学期

### 前学期の求め方（get_prev_term）
- 今が1学期 → 前年の3学期
- 今が2学期 → 今年の1学期
- 今が3学期 → 今年の2学期

### 家事の分割払い
同じ日・同じ家事を複数人がやった場合、単価を人数で割る。  
例: お風呂洗い¥50を2人でやった → 各自¥25

---

## 6. 画面・機能一覧

### ホーム（/）
**未ログイン:** LP（lp.html）を表示  
**親ログイン時:** index_parent.html
- 子供切り替えボタン（今日の家事チェック数バッジ付き）
- 来月の給料予定・現在の所持金
- メニュータイル（日常操作・ボーナス・確認分析）

**子供ログイン時:** index_child.html
- 来月の給料予定・現在の所持金
- ほしいものゴール進捗バー（設定時のみ）
- メニュータイル4つ（家事・成績・収支・実績）

### 家事カレンダー（/chores/）
- カレンダー形式で月別表示
- 各マスにその日の家事チェック状況を色付きバッジで表示
- セルクリック → その日のモーダルで家事を個別にON/OFF
- 今月の家事報酬合計をサマリー行で表示
- 前月・翌月ナビゲーション
- 親は子供切り替え可能（`?child_id=xxx`）

### 成績（/grades/）
- 学期別の成績入力グリッド
- 教科×評価項目3つ（◎〇△）のボタン型入力
- 親が入力開放（grade_input_periods）してから子供も入力可能
- 入力済み学期は色付きバッジ（◎=金・〇=緑・△=グレー）で一覧表示

### 収支表（/finance/）
- 月別の収支一覧
- 日付をタップ → day_detail.html で収入・支出を追加・削除
- カテゴリは自由入力（placeholder: 「給料、お年玉」）

### ほしいものリスト（/goals/）
- 目標商品名・金額・絵文字を登録
- 現在の所持金との差分・達成率プログレスバーを表示
- 達成したら「もう買える！」バッジ
- 子供ホームの先頭にも最優先目標が表示される

### 実績・積み上げ（/stats/）
- 4枚のサマリーカード（総家事回数・家事累計収入・テスト100点回数・ボーナス累計）
- 直近6ヶ月の給料推移バーグラフ（過去5ヶ月 + 来月予定。来月は黄色）
- 今月の家事日数・達成率・先月比
- 最新学期の成績内訳（◎〇△ カウント + プログレスバー）
- 家事種類別先月比テーブル
- 親は子供切り替え可能（`?child_id=xxx`）

### 設定（/admin/）※親専用
- **子供管理:** 追加・編集（名前・学年・パスワード）・削除
- **単価設定:** base_pay・grade_pay_multiplier・eval_excellent/good/poor
- **家事管理:** 追加・編集・削除（論理削除）・並び替え
- **教科管理:** 追加・削除・並び替え
- **プロフィール:** 親の名前・ログインID・メール・パスワード・家族名変更
- **設定プリセット:** スロット1〜3に現在の設定を保存・呼び出し
- **デフォルトに戻す:** admin.pyの`_DEFAULT_*`定数値に一括リセット

### 単価表（/admin/rates）※親専用
- 現在の家事単価一覧
- 成績給の単価一覧

### 給料明細（/admin/payslip）※親専用
- 全子供の月次給料明細を印刷用フォーマットで表示
- 家事項目別件数・報酬・ボーナス内訳
- 月ナビゲーション付き

### テストボーナス入力（/admin/bonus）※親専用
- 子供を選択 → 教科（複数選択可）→ 日付 → 記録
- 1科目あたりの単価 = 学年 × grade_pay_multiplier（学年給と同じ）
- 記録一覧・削除機能あり

### 夏休みボーナス明細（/admin/summer_slip）※親専用
- 夏休み開始日を入力 → 14日以内に全宿題完了で前月給料相当のボーナス
- 付与ボタンで finance_records に `category='summer_bonus'` として記録

### プラン・課金（/billing/）※親専用
- 現在のサブスクリプション状態表示
- Stripe連携で課金処理

### 認証関連
- `/auth/login` — ログイン
- `/auth/logout` — ログアウト
- `/auth/forgot` — パスワードリセット申請（メール送信）
- `/auth/reset/<token>` — パスワード再設定
- `/register/` — 新規登録（30日トライアル開始）

---

## 7. デフォルト設定値

### pay_rates デフォルト（_DEFAULT_PAY_RATES）
```python
{
  'base_pay': 100,
  'grade_pay_multiplier': 50,
  'eval_excellent': 50,
  'eval_good': 15,
  'eval_poor': 0,
}
```

### 家事デフォルト（_DEFAULT_CHORE_TYPES）
| 家事名 | 単価 |
|--------|------|
| テーブル拭き | ¥10 |
| 食器洗い | ¥30 |
| 食器片付け | ¥20 |
| 洗濯物たたみ | ¥30 |
| 洗濯物干し | ¥30 |
| 掃除機かけ | ¥50 |
| ゴミ出し | ¥30 |
| お風呂洗い | ¥50 |
| トイレ掃除 | ¥80 |
| 買い物おつかい | ¥50 |

### 月収シミュレーション（デフォルト単価・小学3年生の場合）
- 学年給: 3年 × ¥50 = ¥150/月
- 成績給（平均的: ◎8・〇10・△6 合計24項目）: ¥50×8 + ¥15×10 = ¥550
- 基本給: ¥100
- 家事報酬: やる日数によって変動（毎日全部: 最大¥330/日）
- → 頑張る子: 給与合計 ¥5,000〜7,000/月程度

---

## 8. 権限設計

| アクセス制御 | デコレータ/ロジック |
|------------|------------------|
| 要ログイン | `@login_required` |
| 親のみ | `@parent_required`（admin.pyで定義） |
| サブスク必須 | `@subscription_required`（utils.pyで定義） |
| 子供のアクセス制御 | `verify_child_ownership(db, child_id)` で family_id 確認 |

子供は自分のデータのみ閲覧・操作可能。  
親は自ファミリーの子供全員のデータを操作可能。

---

## 9. ナビゲーション構成

### デスクトップ（ナビバー）
**親:** ホーム・家事・成績・テストボーナス・収支・給料明細  
**子供:** ホーム・家事・成績・収支・ほしいもの・実績

### スマホ（ボトムナビ、5タブ）
**親:** ホーム・家事・ボーナス・給料明細・設定  
**子供:** ホーム・家事・ほしいもの・収支・実績

---

## 10. 注意事項・既知の挙動

1. **家事報酬の月ズレ:** ホーム画面の「来月の給料予定」は、実際には「今月の家事を来月の給料計算に当てはめた予測」ではなく、「前月の家事記録をベースにした来月給与の計算」。来月分だから今月の家事は反映されない。

2. **成績給の学期ズレ:** 4月に通知表をもらっても、それは1学期の成績なので8月（2学期）の給与から反映される。学期内は前学期の成績で固定。

3. **テストボーナスの月ズレ:** テストボーナスを記録した翌月の給料に反映される（calc_test_bonusは前月の記録を参照）。

4. **compare blueprint** は廃止済み（ファイルは残存するが__init__.pyに登録されていない）。compare/のテンプレートも残存しているが未使用。

5. **家事の分割払い:** 同日・同家事を複数人でやった場合は `unit_price // 人数` で整数除算。端数は切り捨て。

6. **DB初期値とデフォルト値の乖離:** `_seed_if_empty()` の初期値（eval_excellent=150）と`_DEFAULT_PAY_RATES`（eval_excellent=50）が異なる。新規登録時はseed値が入り、デフォルトに戻すと50に更新される。

7. **subjects の is_active:** schema.sql には `is_active` カラムがあるが、初期SQLにない場合あり。ALTER TABLE で追加される可能性に注意。

---

## 11. Jarvis内部API（/jarvis/）

`?key=jarvis-2026` で認証。

| エンドポイント | 内容 |
|--------------|------|
| `/jarvis/stats` | 登録家族数・ユーザー数・アクティブ課金数・収益サマリー |

---

## 12. 積み残し・将来検討事項

- [ ] git push → Render デプロイ（ローカルDockerのみ反映済み、2026-04-24時点）
- [ ] DB本番のpay_rates: eval_excellent が 150 のまま。デフォルトに戻すボタンを押すと ¥50 になる
- [ ] compare.py / compare/ テンプレート の物理削除（未使用だが残存）
- [ ] subjects テーブルの is_active カラムが load_preset 時に UPDATE されるが、schema.sql に明示がない点の整合性確認
