import createClient from "openapi-fetch";
import type { paths } from "./schema";

// 生成的 OpenAPI 路径已含 /api/v1/ 前缀，故 baseUrl 取空串（同源相对）或源地址（跨源 dev）。
const baseUrl = process.env.NEXT_PUBLIC_API_BASE ?? "";

// 强制携带 Cookie（httpOnly 会话）。同源（生产 Caddy）与跨源（本地 dev）均适用；
// 跨源时后端 CORS 已 allow-credentials 并放行 localhost。
const fetchWithCredentials: typeof fetch = (input, init) =>
  fetch(input, { ...init, credentials: "include" });

export const apiClient = createClient<paths>({
  baseUrl,
  fetch: fetchWithCredentials,
});
