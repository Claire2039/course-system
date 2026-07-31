"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/toaster";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

function humanize(
  type: string
): { message: string; tone: "info" | "success" } | null {
  switch (type) {
    case "enrolled":
      return { message: "选课成功", tone: "success" };
    case "waitlisted":
      return { message: "已加入候补队列", tone: "info" };
    case "promoted":
      return { message: "候补转正！", tone: "success" };
    case "dropped":
      return { message: "已退课", tone: "info" };
    default:
      return null;
  }
}

/** 订阅 SSE，事件到达时失效相关查询 + 弹 toast，实现实时座位/状态更新。 */
export function useEventStream(enabled: boolean) {
  const qc = useQueryClient();
  const { toast } = useToast();

  useEffect(() => {
    if (!enabled) return;
    const es = new EventSource(`${BASE}/api/v1/events`, { withCredentials: true });
    es.onmessage = (ev) => {
      try {
        const { type } = JSON.parse(ev.data) as { type: string };
        qc.invalidateQueries({ queryKey: ["sections"] });
        qc.invalidateQueries({ queryKey: ["enrollments"] });
        qc.invalidateQueries({ queryKey: ["waitlist"] });
        qc.invalidateQueries({ queryKey: ["notifications"] });
        const h = humanize(type);
        if (h) toast(h.message, h.tone);
      } catch {
        /* ignore malformed payload */
      }
    };
    return () => es.close();
  }, [enabled, qc, toast]);
}
