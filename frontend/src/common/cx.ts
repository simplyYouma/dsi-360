/** Concatène des classes conditionnelles (ignore false/null/undefined). */
export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ');
}
