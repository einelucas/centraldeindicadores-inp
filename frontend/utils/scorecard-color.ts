export const GENERAL_INDICATOR_COLORS = {
  good: "#609346",
  attention: "#eaa239",
  bad: "#cc5121",
} as const;

export function generalIndicatorColor(value: number): string {
  if (value >= 95) return GENERAL_INDICATOR_COLORS.good;
  if (value >= 70) return GENERAL_INDICATOR_COLORS.attention;
  return GENERAL_INDICATOR_COLORS.bad;
}
