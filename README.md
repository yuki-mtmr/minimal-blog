# 個人サイト

HTML と CSS のみで構築された静的個人サイト。
JavaScript、ビルドプロセス、外部依存はすべて存在しない。

## ファイル構成

```
.
├── index.html
├── about.html
├── style.css
├── posts/
│   ├── index.html
│   └── 2026-05-13-hello-world.html
├── feed.xml
├── robots.txt
├── scripts/
│   └── admin.py        # ローカル専用の執筆/管理 GUI（任意、stdlib only）
└── README.md
```

公開対象は `scripts/` 以外。GitHub Pages 等にデプロイする際は `scripts/` を含めても問題ないが、配信されても誰も実行できないので無害。気になるなら `.gitignore` ではなく **デプロイ除外** にする。

## ローカル確認

サーバ不要：

```sh
open index.html
```

簡易サーバで見たい場合：

```sh
python3 -m http.server 8000
# http://localhost:8000/
```

## 記事の管理（推奨：ローカル管理画面）

執筆・編集・削除を Web フォームで行えるローカル専用の管理画面が `scripts/admin.py` に同梱されている。Python 3 標準ライブラリのみで動く（外部依存なし）。サイト本体は HTML/CSS のままで、Python は執筆時の便利ツールにすぎない。

```sh
python3 scripts/admin.py
# ブラウザが http://127.0.0.1:8765/ で開く
```

機能：

- 記事一覧（編集 / プレビュー / 削除）
- 新規記事フォーム（日付・スラッグ・タイトル・本文）
- 編集フォーム（既存記事の本文を読み込み）
- 「保存してプレビュー」で別タブに描画後の HTML を表示
- 保存・削除のたびに `posts/index.html` / `index.html` / `feed.xml` を自動再生成

本文はプレーンテキスト。**空行で段落が分かれる**（マークダウン等は使わない）。管理画面はローカル `127.0.0.1` にのみバインドされ、外部からは見えない。

オプション：

```sh
python3 scripts/admin.py --port 9000   # ポート変更
python3 scripts/admin.py --no-open     # ブラウザを自動で開かない
```

## 手動で記事を追加する場合

管理画面を使わずに手で書く手順：

1. `posts/` 配下に `YYYY-MM-DD-slug.html` で作成
2. 既存記事 (`posts/2026-05-13-hello-world.html`) をコピーして書き換え
3. `posts/index.html` の該当年セクションに日付降順で 1 行追加
4. `index.html` の「最新の記事」も必要に応じて更新
5. `feed.xml` に新しい `<item>` を追加（後述）

## RSS の更新

`feed.xml` の `<channel>` 直下、既存の `<item>` の上に新しい `<item>` を追加する。

```xml
<item>
  <title>記事タイトル</title>
  <link>https://example.com/posts/YYYY-MM-DD-slug.html</link>
  <guid>https://example.com/posts/YYYY-MM-DD-slug.html</guid>
  <pubDate>Wed, 13 May 2026 00:00:00 +0900</pubDate>
  <description>記事の要約。</description>
</item>
```

`<lastBuildDate>` も最新記事の日付に合わせて更新する。

## デプロイ

### GitHub Pages

1. リポジトリを作成し、このディレクトリの全ファイルを push する
2. リポジトリの Settings → Pages を開く
3. Source を `Deploy from a branch` にし、`main` ブランチ / `/ (root)` を選ぶ
4. 数十秒待つと `https://USERNAME.github.io/REPO/` で公開される

`example.com` を実ドメインに置換する場合は `feed.xml` 内の URL も更新すること。

### Cloudflare Pages

1. Cloudflare ダッシュボードで Pages → Create application を開く
2. Connect to Git で当該リポジトリを選択する
3. Build command は空、Build output directory は `/`（ルート）に設定する
4. Deploy を実行する

## サイトの設計方針

- 単一カラム、最大幅 40em
- システムフォントのみ。Web フォントは読み込まない
- アクセス解析、コメント欄、シェアボタンを置かない
- ボーダー・シャドウ・アニメーションなどの装飾を置かない
- ダークモードは `prefers-color-scheme` で OS 設定に追従
- 30 年後も同じように読めることを目指す
