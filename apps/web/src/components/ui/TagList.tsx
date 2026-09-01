/**
 * A wrapped list of short atoms: capabilities, scopes, tools, traits.
 * `mono` marks machine identifiers; `suffix` appends `()` for tool names.
 */
export function TagList({
  items,
  mono = false,
  suffix = "",
  emptyLabel,
}: {
  items: string[];
  mono?: boolean;
  suffix?: string;
  emptyLabel?: string;
}) {
  if (items.length === 0) {
    return emptyLabel ? (
      <span className="t-small text-ink-3">{emptyLabel}</span>
    ) : null;
  }
  return (
    <ul className="flex flex-wrap gap-1.5 list-none">
      {items.map((item) => (
        <li
          key={item}
          className={`inset px-2 py-0.5 text-ink-1 ${mono ? "t-mono" : "t-small"}`}
        >
          {item}
          {suffix}
        </li>
      ))}
    </ul>
  );
}
