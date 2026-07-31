/** 从 openapi-fetch 的 error 里安全提取 detail.message（后端 HTTPException 的形状）。 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail?: unknown }).detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      const m = (detail as { message?: unknown }).message;
      if (typeof m === "string") return m;
    }
    if (typeof detail === "string") return detail;
  }
  return fallback;
}
