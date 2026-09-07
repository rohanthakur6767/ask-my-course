import { useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

// A small CSS/SVG crest, no external assets: a shield with a serif monogram.
function Crest() {
  return (
    <svg className="crest" width="38" height="42" viewBox="0 0 38 42" aria-hidden="true">
      <path
        d="M19 2 L34 7 L34 21 C34 31 27 37 19 40 C11 37 4 31 4 21 L4 7 Z"
        fill="rgba(255,255,255,0.05)" stroke="#C9A24E" strokeWidth="1.5"
      />
      <text
        x="19" y="27" textAnchor="middle"
        fontFamily="'Source Serif 4', Georgia, serif" fontSize="18" fontWeight="600" fill="#C9A24E"
      >A</text>
    </svg>
  );
}

function IconTeacher() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 8 L12 4 L21 8 L12 12 Z" />
      <path d="M6 10.5 V15 C6 16.4 8.7 17.8 12 17.8 C15.3 17.8 18 16.4 18 15 V10.5" />
      <path d="M21 8 V13" />
    </svg>
  );
}

function IconStudent() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 5 H19 A2 2 0 0 1 21 7 V14 A2 2 0 0 1 19 16 H12 L8 20 V16 H5 A2 2 0 0 1 3 14 V7 A2 2 0 0 1 5 5 Z" />
      <path d="M9.5 9.2 A2.4 2.4 0 0 1 14.2 9.8 C14.2 11.2 12 11.4 12 12.6" />
      <path d="M12 14.4 L12 14.5" />
    </svg>
  );
}

const SECTIONS = [
  { prefix: "/teacher", label: "Teacher workspace" },
  { prefix: "/student", label: "Student" },
];

export default function Layout({ children }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const close = () => setOpen(false);
  const title = (SECTIONS.find((s) => pathname.startsWith(s.prefix)) || {}).label || "Ask My Course";

  return (
    <div className="shell" data-open={open}>
      <aside className="sidebar">
        <Link to="/teacher" className="brand" onClick={close}>
          <Crest />
          <span className="brand-text">
            <span className="brand-name">Ask My Course</span>
            <span className="brand-sub">Eagle LMS</span>
          </span>
        </Link>

        <nav className="side-nav">
          <div className="side-group">
            <div className="side-label">Workspace</div>
            <NavLink to="/teacher" className="side-link" onClick={close}>
              <IconTeacher /> Teacher
            </NavLink>
            <NavLink to="/student" className="side-link" onClick={close}>
              <IconStudent /> Student
            </NavLink>
          </div>
        </nav>

        <div className="side-foot">Ask My Course · demo</div>
      </aside>

      <div className="backdrop" onClick={close} />

      <div className="main">
        <header className="topbar">
          <button className="menu-btn" onClick={() => setOpen((o) => !o)} aria-label="Toggle menu">≡</button>
          <span className="topbar-title">{title}</span>
          <span className="user-chip"><span className="ini" aria-hidden="true">DS</span> Demo School</span>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
