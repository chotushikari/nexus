"use client";

import { type ReactNode, useState } from "react";
import { ChevronRight } from "lucide-react";

/**
 * Progressive disclosure for payloads and metadata. Collapsed by default so
 * a timeline stays readable; the summary line states what is hidden.
 */
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
}: {
  summary: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 t-label hover:text-ink-1 transition-colors"
      >
        <ChevronRight
          size={12}
          strokeWidth={2}
          aria-hidden="true"
          className="transition-transform"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        />
        {summary}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </div>
  );
}
