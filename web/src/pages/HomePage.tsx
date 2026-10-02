import { Link } from "react-router-dom";

export default function HomePage() {
  return (
    <section className="hero-panel">
      <p className="eyebrow">シミュレーション工学 · 教室実験</p>
      <h1>スマホ蛍</h1>
      <p className="lede">
        タップして音を出し、教室の物理音でリズムを同期させる実験アプリです。
        収集したタップデータは位相振動子シミュレーションで再現できます。
      </p>
      <div className="cta-row">
        <Link className="btn primary" to="/join">
          参加する
        </Link>
      </div>
      <ol className="steps">
        <li>講師がセッションを作成し、QR / コードを共有</li>
        <li>席番号（例: A2）を入力して参加</li>
        <li>実験1（無音）→ 実験2（音あり）でタップ</li>
        <li>データを書き出し、シミュレーションで同期を再現</li>
      </ol>
    </section>
  );
}
