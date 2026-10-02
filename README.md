# スマホ蛍 (SmartPhone Hotaru)

シミュレーション工学の教室実験用アプリです。スマホをタップして音を出し、教室の物理音でリズム同期を観察します。収集データは位相振動子モデルで再現・予測できます。

## 構成

```
SmartPhoneHotal/
  web/       Vite + React 実験 UI（参加 / タップ / 講師）
  server/    Express + Socket.IO（セッション・ログ集約）
  sim/       Python 位相振動子シミュレーション
  shared/    JSON スキーマ
  material/  授業資料
```

## 必要環境

- Node.js 20+（リポジトリに `.tools/node` がある場合はそれを利用可）
- Python 3.11+
- 依存: `sim/requirements.txt`（numpy, matplotlib）

## セットアップ

```powershell
# Node（PATH に無い場合）
$env:PATH = "$PWD\.tools\node;$env:PATH"
$env:NODE_TLS_REJECT_UNAUTHORIZED = "0"   # 社内プロキシ等で証明書エラーになる場合のみ

cd server; npm install; cd ..
cd web; npm install; cd ..
pip install -r sim/requirements.txt
```

## 起動（開発）

ターミナル1 — API / WebSocket:

```powershell
$env:PATH = "$PWD\.tools\node;$env:PATH"
npm run dev:server
```

ターミナル2 — フロント:

```powershell
$env:PATH = "$PWD\.tools\node;$env:PATH"
npm run dev:web
```

- 参加者 UI: http://localhost:5173 （ナビに「参加」のみ）
- 講師画面: http://localhost:5173/instructor （リンク非表示・URL 直打ち）
- API: http://localhost:3001

### 授業当日の流れ

1. 講師が `/instructor` を開きセッション作成 → QR / コードを共有
2. 学生は席番号（例: `A2`）を入力して参加
3. **実験1**（無音）→ 約15秒タップ → 停止（ベース周波数）
4. **実験2**（音あり）→ 約15秒タップ → 停止（同期の観察）
5. JSON / CSV をダウンロード

結合はネットではなく**教室の物理音**です。サーバは開始合図とタップログ収集のみ行います。

## シミュレーション UI（NiceGUI）

授業中はコマンド入力なしで使えます。

```powershell
pip install -r sim/requirements.txt
python -m sim.ui
```

または `run_sim_ui.bat` をダブルクリック。ブラウザが開き、次が使えます。

1. **実験確認** — 時間窓を指定して周波数分布を見て、ω を採用  
2. **時間発展** — 2D 発光・sinφ・ポアンカレ位相差・R(t)  
3. **分析** — 過渡後の実効周波数分布（実験2と重ね描き）  
4. **検証** — a=0 の理論比較、2振動子結合  

詳細仕様: [docs/sim-ui-spec.md](docs/sim-ui-spec.md)

### CLI（従来）

デモ（合成データで `a=0, 0.3, 1` をスイープ）:

```powershell
python -m sim.run --demo --save-demo shared/sample-session.json
python sim/plot_results.py
```

実測 JSON:

```powershell
python -m sim.run path/to/hotaru-ABCD.json -o sim/output/class_run.json
python sim/plot_results.py sim/output/class_run.json
```

モデル:

\[
\dot\phi_i = \omega_i + \sum_j \frac{a}{r_{ij}}\sin(\phi_j - \phi_i)
\]

- `ω_i` は実験1のタップ周期から算出
- 席座標は机 2 m 格子・同一机内 1 m（資料どおり）
- `a=0` でばらつき、`a=1` で同期、中間でクラスター傾向を確認

## 本番ビルド（ローカル確認）

```powershell
npm run build:prod
npm start
```

サーバが `web/dist` を配信します（http://localhost:3001）。

## クラウド公開（Render・無料）

授業で学生のスマホから使う場合は、**Render** へのデプロイを推奨します。

→ 手順はこちら: **[docs/render-deploy.md](docs/render-deploy.md)**

要点だけ先に:

| 項目 | 値 |
|------|-----|
| Build Command | `npm run build:prod` |
| Start Command | `npm start` |
| Plan | Free |
| 設定ファイル | [`render.yaml`](render.yaml) |

> **補足:** Render では `NODE_ENV=production` のため、ビルド時は `npm install --include=dev` で TypeScript / Vite / `@types/*` も入れます（`build:prod` に含まれています）。

無料枠はアイドル時にスリープします。授業数分前に講師が URL を開いて起こしてください。
