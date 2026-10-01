# Render へのデプロイ手順（初心者向け）

スマホ蛍を **無料の Render** に公開し、教室の学生がスマホから同じ URL で使えるようにする手順です。

完成イメージ:

- 公開 URL 例: `https://smartphone-hotaru.onrender.com`
- 講師も学生も、その URL をブラウザで開くだけ
- HTTPS 付き（スマホでも安心）

---

## 0. 全体の流れ（先に把握）

1. このプロジェクトを **GitHub** に置く  
2. **Render** でそのリポジトリを読み込む  
3. ビルドが成功すると URL が発行される  
4. 授業ではその URL を使う  

所要時間の目安: 初回 20〜40 分（GitHub / Render のアカウント作成含む）

---

## 1. 事前に用意するもの

- [ ] Google や GitHub のアカウント（ログイン用）
- [ ] この `SmartPhoneHotal` プロジェクトの最新コード
- [ ] （任意）GitHub Desktop、または Cursor / VS Code の Git 機能

専門知識は不要です。「GitHub に置き → Render につなぐ」だけ覚えれば大丈夫です。

---

## 2. GitHub にコードを上げる

### 2-1. GitHub で空のリポジトリを作る

1. https://github.com にログイン  
2. 右上 **+** → **New repository**  
3. Repository name 例: `SmartPhoneHotal`  
4. **Public** でよい（授業用なら Public が簡単）  
5. **Add a README** などは **チェックしない**（すでにローカルにコードがあるため）  
6. **Create repository**

### 2-2. ローカルから push する

PowerShell でプロジェクト直下に移動して実行します（まだ git 初期化していない場合）:

```powershell
cd C:\Users\cursol-user\Projects\SmartPhoneHotal

git init
git add .
git commit -m "Initial commit: スマホ蛍 web + sim"
git branch -M main
git remote add origin https://github.com/<あなたのユーザー名>/SmartPhoneHotal.git
git push -u origin main
```

`<あなたのユーザー名>` は自分の GitHub 名に置き換えてください。

すでに GitHub リポジトリがある場合は、変更を commit して `git push` するだけで十分です。

> **認証で止まったとき**  
> GitHub はパスワード代わりに **Personal Access Token** や **GitHub CLI / Desktop** のログインが必要です。ブラウザで GitHub Desktop を使うのがいちばん簡単です。

---

## 3. Render アカウントを作る

1. https://render.com を開く  
2. **Get Started** → **GitHub** でサインアップ（おすすめ）  
3. GitHub 連携を求められたら、このリポジトリへのアクセスを許可する  

---

## 4. Web Service を作る（手動設定）

Blueprint（`render.yaml`）を使う方法と、画面で手動作成する方法があります。初めてなら **手動** が分かりやすいです。

### 4-1. 新規作成

1. Render の Dashboard で **New +** → **Web Service**  
2. 対象の GitHub リポジトリ `SmartPhoneHotal` を選ぶ  
3. 必要なら **Connect account / Configure account** でリポジトリ権限を付与  

### 4-2. 設定値（そのままコピーしてよい）

| 項目 | 入力する内容 |
|------|----------------|
| Name | `smartphone-hotaru`（任意） |
| Region | `Singapore` などアジア寄りの地域 |
| Branch | `main` |
| Root Directory | （空欄のまま） |
| Runtime | `Node` |
| Build Command | `npm run build:prod` |
| Start Command | `npm start` |
| Instance Type | **Free** |

### 4-3. 環境変数（Environment）

**Add Environment Variable** で次を追加します。

| Key | Value |
|-----|--------|
| `NODE_VERSION` | `20` |
| `NODE_ENV` | `production` |

> `PORT` は Render が自動で渡すので、自分で設定しなくて大丈夫です。

### 4-4. デプロイ

**Create Web Service**（または **Deploy**）を押します。  
初回ビルドは数分かかります。ログに `Hotaru server listening on port ...` が出れば成功です。

成功すると、画面上部に次のような URL が出ます。

```text
https://smartphone-hotaru.onrender.com
```

（名前によって違います。自分の URL を控えてください。）

---

## 5. Blueprint（render.yaml）で作る場合

リポジトリに [`render.yaml`](../render.yaml) があります。

1. Render Dashboard → **New +** → **Blueprint**  
2. この GitHub リポジトリを選択  
3. 表示された Web Service を確認して Apply  

手動設定と同じ内容（無料プラン・ビルド / 起動コマンド）が入っています。

---

## 6. 動作確認

ブラウザで公開 URL を開き、次を確認します。

1. トップページ「スマホ蛍」が表示される  
2. **講師** → セッション作成 → コードと QR が出る  
3. スマホで同じ URL を開き **参加** → 席番号（例: `A2`）を入力  
4. 講師が **実験1 開始** → スマホでタップすると音が出る  
5. `https://（あなたのURL）/api/health` を開くと `{"ok":true}` と出る  

QR は公開 URL 向けに自動生成されます（講師画面の QR を学生に見せれば OK）。

---

## 7. 授業当日の使い方

1. **開始 3〜5 分前**に講師が公開 URL を開く（無料枠の「スリープ」解除）  
2. セッションを作成し、QR / コードを共有  
3. 実験1 → 実験2 → JSON/CSV ダウンロード  
4. シミュレーションは講師 PC で `python -m sim.run ダウンロードした.json`  

詳細な実験手順は [README.md](../README.md) を参照してください。

---

## 8. 無料枠で起きやすいこと

### しばらく使うと遅い / 最初だけ待たされる

無料プランは、アクセスが無いとサービスが **スリープ** します。  
起こすのに数十秒かかることがあります。

**対策:** 授業の少し前に講師がサイトを一度開く。

### デプロイし直すとセッションが消える

タップデータはサーバのメモリ上にあります。再起動すると消え、JSON を取っていない分は復元できません。

**対策:** 実験が終わったらすぐ JSON / CSV を保存する。

### ビルドが赤いエラーで止まった

Render の **Logs** を開きます。よくある原因:

- Build Command の打ち間違い（`npm run build:prod` になっているか）
- GitHub に最新コードが push されていない
- Node バージョン（`NODE_VERSION=20` を入れたか）

ローカルで同じビルドを試す:

```powershell
cd C:\Users\cursol-user\Projects\SmartPhoneHotal
$env:PATH = "$PWD\.tools\node;$env:PATH"
npm run build:prod
npm start
```

http://localhost:3001 で動けば、コード側は問題ない可能性が高いです。

### Socket（リアルタイム）が繋がらない

同一 URL で画面と API を配信している構成なので、通常は追加設定不要です。  
それでもダメなときは:

- スマホのプライベート DNS / 学内プロキシを疑う
- 別回線（テザリング）で試す
- Render のサービスが起動中か（スリープしていないか）を確認する

---

## 9. 更新のしかた（2回目以降）

コードを直したら:

```powershell
git add .
git commit -m "説明メッセージ"
git push
```

Render は `main` への push を検知して **自動で再デプロイ** します（Auto-Deploy が On の場合）。

---

## 10. 設定の要約（チートシート）

| 項目 | 値 |
|------|-----|
| Build Command | `npm run build:prod` |
| Start Command | `npm start` |
| Health Check | `/api/health` |
| Node | 20 |
| Plan | Free |
| 設定ファイル | リポジトリ直下の `render.yaml` |

これで、ローカル開発と同じアプリを、教室全体から使える公開サイトにできます。
