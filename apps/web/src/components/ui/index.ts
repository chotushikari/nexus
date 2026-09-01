/**
 * Shared visual primitives for the NEXUS operator surfaces.
 *
 * Every one of these consumes tokens from `src/app/globals.css`. If a page
 * needs a colour, it comes from a `Tone` in `src/lib/format.ts` — never a hex
 * literal in a component.
 */

export { Badge, LabelledBadge } from "./Badge";
export { CodeBlock } from "./CodeBlock";
export { Disclosure } from "./Disclosure";
export { EmptyState, ErrorState, LoadingState } from "./EmptyState";
export { KeyValue, type KeyValueRow } from "./KeyValue";
export { Inset, Panel, PanelBody, PanelHeader } from "./Panel";
export { ProgressBar } from "./ProgressBar";
export { PageHeader, SectionLabel } from "./SectionLabel";
export { SearchInput } from "./SearchInput";
export { SegmentedControl, type SegmentOption } from "./SegmentedControl";
export { InlineStat, StatCard } from "./StatCard";
export { TagList } from "./TagList";
