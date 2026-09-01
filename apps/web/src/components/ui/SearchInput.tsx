"use client";

import { Search, X } from "lucide-react";

/** Search field with a leading glyph and an explicit clear affordance. */
export function SearchInput({
  value,
  onChange,
  placeholder = "Search",
  label,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  /** Accessible name; visually hidden. */
  label?: string;
}) {
  return (
    <div className="relative">
      <Search
        size={14}
        strokeWidth={1.75}
        aria-hidden="true"
        className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3 pointer-events-none"
      />
      <input
        type="search"
        className="input pl-9 pr-9"
        value={value}
        aria-label={label ?? placeholder}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      {value !== "" && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Clear search"
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink-1"
        >
          <X size={14} strokeWidth={2} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
