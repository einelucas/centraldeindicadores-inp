/** Porte de src/lib/browser-events.ts (repositório de referência). */

export const INDICATOR_DATA_CHANGED_EVENT = "indicator:data-changed";

export function notifyIndicatorDataChanged(): void {
  window.dispatchEvent(new Event(INDICATOR_DATA_CHANGED_EVENT));
}
