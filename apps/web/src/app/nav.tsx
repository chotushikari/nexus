"use client";

import { useEffect, useState } from "react";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/agents", label: "Agents" },
  { href: "/approvals", label: "Approvals" },
  { href: "/security", label: "Security" },
];

export default function Nav() {
  const [backendOk, setBackendOk] = useState(false);
  const [current, setCurrent] = useState("/");

  useEffect(() => {
    setCurrent(window.location.pathname);
    fetch("http://localhost:8000/api/health")
      .then((r) => r.ok && setBackendOk(true))
      .catch(() => setBackendOk(false));
  }, []);

  return (
    <header
      className="sticky top-0 z-50 flex items-center justify-between px-6 py-3 border-b"
      style={{
        background: "rgba(10,15,30,0.95)",
        backdropFilter: "blur(16px)",
        borderColor: "var(--nexus-border)",
      }}
    >
      {/* Brand */}
      <a href="/" className="flex items-center gap-3 no-underline">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center font-black text-white text-sm"
          style={{
            background: "linear-gradient(135deg, #6366f1, #06b6d4)",
            boxShadow: "0 0 16px rgba(99,102,241,0.5)",
          }}
        >
          N
        </div>
        <span className="font-bold text-lg tracking-tight" style={{ color: "#6366f1" }}>
          NEXUS
        </span>
        <span
          className="text-xs px-2 py-0.5 rounded-full font-medium"
          style={{
            background: "rgba(99,102,241,0.15)",
            color: "#6366f1",
            border: "1px solid rgba(99,102,241,0.3)",
          }}
        >
          Enterprise OS
        </span>
      </a>

      {/* Nav links */}
      <nav className="flex items-center gap-1">
        {LINKS.map(({ href, label }) => {
          const active = current === href || (href !== "/" && current.startsWith(href));
          return (
            <a
              key={href}
              href={href}
              className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all"
              style={{
                color: active ? "#6366f1" : "var(--nexus-muted)",
                background: active ? "rgba(99,102,241,0.12)" : "transparent",
                border: active ? "1px solid rgba(99,102,241,0.25)" : "1px solid transparent",
                textDecoration: "none",
              }}
            >
              {label}
            </a>
          );
        })}
      </nav>

      {/* Backend status */}
      <div className="flex items-center gap-2 text-xs" style={{ color: "var(--nexus-muted)" }}>
        <span
          className="w-2 h-2 rounded-full"
          style={{
            background: backendOk ? "#10b981" : "#ef4444",
            boxShadow: backendOk ? "0 0 6px #10b981" : "0 0 6px #ef4444",
          }}
        />
        {backendOk ? "API Online" : "API Offline"}
      </div>
    </header>
  );
}
