import { Link, Navigate, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import JoinPage from "./pages/JoinPage";
import PlayPage from "./pages/PlayPage";
import InstructorPage from "./pages/InstructorPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand">
          スマホ蛍
        </Link>
        <nav className="nav">
          <Link to="/join">参加</Link>
          <Link to="/instructor">講師</Link>
        </nav>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/join" element={<JoinPage />} />
          <Route path="/join/:code" element={<JoinPage />} />
          <Route path="/play" element={<PlayPage />} />
          <Route path="/instructor" element={<InstructorPage />} />
          <Route path="/instructor/:code" element={<InstructorPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
