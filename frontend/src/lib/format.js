export const number = (value) => new Intl.NumberFormat().format(value);
export const percent = (value) =>
  value == null ? "—" : `${value.toFixed(1)}%`;
export function date(value, withTime = false) {
  if (!value) return "Date unavailable";
  const normalized = /^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/.test(value)
    ? value.replace(" ", "T") + "Z"
    : value;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}
