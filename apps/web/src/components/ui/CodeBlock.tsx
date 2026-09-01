import { prettyJson } from "@/lib/format";

/** Monospace payload block. Paper, never a dark slab on a light page. */
export function CodeBlock({
  value,
  maxHeight = "18rem",
  className = "",
}: {
  /** Raw string, or any JSON-serialisable value. */
  value: unknown;
  maxHeight?: string;
  className?: string;
}) {
  const text = typeof value === "string" ? value : prettyJson(value);
  return (
    <pre
      className={`code-block whitespace-pre-wrap ${className}`.trim()}
      style={{ maxHeight, overflowY: "auto" }}
    >
      {text}
    </pre>
  );
}
