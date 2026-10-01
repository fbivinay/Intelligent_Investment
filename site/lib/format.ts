const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const rupees = (v: number) => inr.format(v);
export const rupeesExact = (v: number) => inr2.format(v);
export const pct = (v: number, digits = 1) => `${(v * 100).toFixed(digits)}%`;

/** A short form for chart axes: 12.5 L, 1.2 Cr. */
export function short(v: number): string {
  if (Math.abs(v) >= 1e7) return `${(v / 1e7).toFixed(2)} Cr`;
  if (Math.abs(v) >= 1e5) return `${(v / 1e5).toFixed(1)} L`;
  return inr.format(v);
}

export function years(start: string, end: string): number {
  return (Date.parse(end) - Date.parse(start)) / (365.25 * 86400000);
}

export function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
