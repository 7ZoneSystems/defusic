/**
 * Resolve a CSS custom property value from the computed styles of <html>.
 * Used for canvas drawing where CSS variables are not directly available.
 */
export function resolveToken(name: string): string {
  if (typeof window === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * Resolve multiple tokens at once.
 */
export function resolveTokens(names: string[]): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const style = getComputedStyle(document.documentElement);
  const result: Record<string, string> = {};
  for (const name of names) {
    result[name] = style.getPropertyValue(name).trim();
  }
  return result;
}

/**
 * Resolve a CSS var to an rgba(r, g, b, alpha) string.
 * Useful for canvas where you need alpha variants of theme colors.
 */
export function resolveTokenAlpha(name: string, alpha: number): string {
  const hex = resolveToken(name);
  if (!hex) return `rgba(0,0,0,${alpha})`;
  const rgb = hexToRgb(hex);
  if (!rgb) return `rgba(0,0,0,${alpha})`;
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const h = hex.replace('#', '');
  if (h.length === 3) {
    const r = parseInt(h[0] + h[0], 16);
    const g = parseInt(h[1] + h[1], 16);
    const b = parseInt(h[2] + h[2], 16);
    return { r, g, b };
  }
  if (h.length === 6) {
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    return { r, g, b };
  }
  return null;
}
