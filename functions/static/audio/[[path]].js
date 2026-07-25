import { SECURITY_HEADERS } from "../../_shared/response.js";


export function onRequest() {
  return new Response("Gone.", {
    status: 410,
    headers: {
      ...SECURITY_HEADERS,
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex",
    },
  });
}
