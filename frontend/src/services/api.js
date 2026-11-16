export class ApiError extends Error {
  constructor(message, status, code = "request_failed") {
    super(message);
    this.status = status;
    this.code = code;
  }
}
export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(
      "Unable to reach PublicPulse. Check that the backend is running, then retry.",
      0,
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok || !body || !("data" in body))
    throw new ApiError(
      body?.error?.message || "The backend is unavailable. Please retry.",
      response.status,
      body?.error?.code,
    );
  return body.data;
}
export const post = (path, data = {}) =>
  api(path, { method: "POST", body: JSON.stringify(data) });
export function params(values) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return query.toString();
}
