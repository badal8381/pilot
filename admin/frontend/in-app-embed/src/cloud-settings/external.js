// Open a server-provided URL in a new tab, but only when it is http(s). Guards
// against a `javascript:` / `data:` URL from a compromised upstream (gateway,
// pilot) turning an "open checkout" into script execution in the desk page.
export function openExternal(url) {
  if (!url) return;
  let parsed;
  try {
    parsed = new URL(url, window.location.origin);
  } catch {
    return;
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return;
  window.open(parsed.href, "_blank", "noopener");
}
