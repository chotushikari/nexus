import type { Metadata } from "next";
import "./globals.css";
import Nav from "./nav";

export const metadata: Metadata = {
  title: "NEXUS – Autonomous Enterprise Operating Environment",
  description:
    "Governed multi-agent platform: real-time mission control, policy enforcement, human-in-the-loop approvals, and full audit observability.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col" style={{ background: "var(--nexus-bg)" }}>
        <Nav />
        <main className="flex-1 p-6">{children}</main>
        <footer
          className="px-6 py-3 text-center text-xs border-t"
          style={{ borderColor: "var(--nexus-border)", color: "var(--nexus-muted)" }}
        >
          NEXUS v0.1 · Google ADK + Gemini + Firestore · Track 3 Hackathon
        </footer>
      </body>
    </html>
  );
}
