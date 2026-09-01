import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

/**
 * The empty state carries the instruction, not an apology. `hint` should tell
 * the operator exactly what action produces data here.
 */
export function EmptyState({
  icon: Icon,
  title,
  hint,
  action,
  compact = false,
}: {
  icon?: LucideIcon;
  title: string;
  hint?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${
        compact ? "py-8 px-4" : "py-16 px-6"
      }`}
    >
      {Icon && (
        <Icon
          size={compact ? 18 : 22}
          strokeWidth={1.5}
          className="text-ink-3 mb-3"
          aria-hidden="true"
        />
      )}
      <div className="t-body font-medium text-ink-1">{title}</div>
      {hint && <div className="t-small text-ink-2 mt-1.5 max-w-md">{hint}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Loading placeholder. Text, not a spinner — the wait is usually sub-second. */
export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="py-12 text-center t-small text-ink-2" role="status">
      {label}…
    </div>
  );
}

/** A failed fetch is a fact, not a crash. Show it and offer a retry. */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="py-12 px-6 text-center">
      <div className="t-body font-medium" style={{ color: "var(--state-danger)" }}>
        Request failed
      </div>
      <div className="t-small text-ink-2 mt-1.5 break-words max-w-lg mx-auto">{message}</div>
      {onRetry && (
        <button type="button" className="btn mt-4" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
