import type { Metadata } from "next";
import "./globals.css";
import Nav from "./nav";

export const metadata: Metadata = {
  title: "NEXUS — Autonomous Enterprise Operating Environment",
  description:
    "Governed multi-agent operations: mission control, least-privilege policy enforcement, human-in-the-loop approvals, and a complete audit record.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-paper-1 text-ink-0">
        <Nav />
        <main className="flex-1 px-6 py-8">{children}</main>
        <footer className="px-6 py-4 border-t border-paper-3">
          <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
            <span className="t-label">
              NEXUS · Governed autonomous enterprise operations
            </span>
            <span className="t-label">
              Every action is policy-checked and recorded in the mission audit
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
