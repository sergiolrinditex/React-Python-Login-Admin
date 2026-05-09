/**
 * Design system barrel — Hilo People.
 *
 * What: Re-exports all design system primitives from a single entry point so
 * feature components can import from '@/shared/design-system' without knowing
 * individual file paths.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Components shipped in this slice:
 *   Wordmark, TrackedLabel, StatusDot, EditorialInput, SolidCTA,
 *   HairlineTable, MobileFrame, AdminShell
 *
 * Deferred (downstream slices):
 *   CitationInline — P03-S02 (chat citations feature)
 */

export { Wordmark } from './Wordmark';
export { TrackedLabel } from './TrackedLabel';
export { StatusDot } from './StatusDot';
export { EditorialInput } from './EditorialInput';
export { SolidCTA } from './SolidCTA';
export { HairlineTable } from './HairlineTable';
export { MobileFrame } from './MobileFrame';
export { AdminShell } from './AdminShell';
