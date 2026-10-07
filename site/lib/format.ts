// Indian money and dates as people read them: ₹63,10,228, ₹63.1 lakh, ₹1.24 crore, 3 Apr 2017.

const IN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export const inr = (n: number) => `${n < 0 ? "−" : ""}₹${IN.format(Math.abs(Math.round(n)))}`;

/** ₹63.1 lakh, ₹1.73 lakh, ₹1.24 crore, ₹48,500: the short form for figures (two decimals under ₹10 lakh unless `digits` says otherwise). */
export function money(n: number, digits?: number) {
  const a = Math.abs(n), s = n < 0 ? "−" : "";
  if (a >= 1e7) return `${s}₹${+(a / 1e7).toFixed(digits ?? 2)} crore`;
  if (a >= 1e5) return `${s}₹${(a / 1e5).toFixed(digits ?? (a < 1e6 ? 2 : 1)).replace(/\.0+$/, "")} lakh`;
  return `${s}₹${IN.format(Math.round(a))}`;
}

/** ₹63L, ₹1.2Cr: axis ticks. */
export function tick(n: number) {
  const a = Math.abs(n), s = n < 0 ? "−" : "";
  if (a >= 1e7) return `${s}₹${+(a / 1e7).toFixed(2)}Cr`;
  if (a >= 1e5) return `${s}₹${+(a / 1e5).toFixed(1)}L`;
  if (a >= 1e3) return `${s}₹${+(a / 1e3).toFixed(0)}k`;
  return `${s}₹${Math.round(a)}`;
}

export const pct = (x: number, d = 1) => `${x < 0 ? "−" : ""}${Math.abs(x * 100).toFixed(d)}%`;
export const signed = (x: number, d = 1) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x * 100).toFixed(d)}%`;
export const count = (n: number) => IN.format(n);

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export function day(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}
export function month(iso: string, long = false) {
  const [y, m] = iso.split("-").map(Number);
  return `${(long ? LONG : MONTHS)[m - 1]} ${y}`;
}

/** 9.5 years, 3 years, 8 months. */
export function span(fromIso: string, toIso: string) {
  const days = (Date.parse(toIso) - Date.parse(fromIso)) / 864e5;
  const years = days / 365.25;
  if (years >= 1) return `${+years.toFixed(1)} year${years === 1 ? "" : "s"}`;
  const months = Math.round(days / 30.44);
  return `${months} month${months === 1 ? "" : "s"}`;
}
