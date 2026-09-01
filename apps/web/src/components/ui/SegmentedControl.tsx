"use client";

export interface SegmentOption<T extends string | number> {
  value: T;
  label: string;
  /** Optional trailing count. */
  count?: number;
}

/**
 * Single-select filter row. Selection is carried by weight and an ink
 * underline, not by hue — filters are navigation, not runtime state.
 */
export function SegmentedControl<T extends string | number>({
  options,
  value,
  onChange,
  label,
  grow = false,
}: {
  options: SegmentOption<T>[];
  value: T;
  onChange: (next: T) => void;
  label: string;
  /** Stretch segments to fill the row. */
  grow?: boolean;
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className="inline-flex items-stretch gap-1 p-0.5 inset w-full"
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={String(option.value)}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(option.value)}
            className={`${
              grow ? "flex-1" : ""
            } inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded t-small font-semibold transition-colors ${
              selected
                ? "bg-paper-0 text-ink-0 shadow-1"
                : "text-ink-2 hover:text-ink-0"
            }`}
          >
            {option.label}
            {typeof option.count === "number" && (
              <span className="t-mono text-ink-3">{option.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
