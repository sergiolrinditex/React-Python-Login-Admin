/**
 * Hilo People — i18n TypeScript type augmentation.
 *
 * Slice/Phase: P00-S01-T005 — i18n resources ES/EN/FR / Phase 0 Scaffold.
 *
 * Responsibility: augment the `i18next` module with CustomTypeOptions so that
 *   downstream consumers get type-safe `t()` calls and namespace inference.
 *   This is a BEST PRACTICE — not required for runtime, but prevents silent
 *   key typos in downstream feature screens (P03-*).
 *
 * Note: this file declares the shape at the root level for each namespace.
 *   When new keys are added to resources, update the type here too.
 *
 * Key deps: i18next ^26.1.0 (CustomTypeOptions stable since v23).
 * Source ref: task pack §8.3 "Decisión: Yes mínima".
 */

import type { I18N_NAMESPACES } from "./languages";

type NS = (typeof I18N_NAMESPACES)[number];

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "common";
    ns: NS;
  }
}
