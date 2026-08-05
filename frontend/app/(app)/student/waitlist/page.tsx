"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function WaitlistPage() {
  const q = useQuery({
    queryKey: ["waitlist"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/me/waitlist");
      if (!data) throw new Error("加载失败");
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">我的候补</h1>
      <div className="space-y-2">
        {q.isLoading && <p className="text-muted-foreground">加载中…</p>}
        {q.isError && <p className="text-destructive">加载失败，请刷新重试。</p>}
        {(q.data ?? []).map((e) => (
          <Card key={e.id}>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <span className="font-mono text-xs text-muted-foreground">
                  {e.section.course.code}
                </span>{" "}
                <span className="font-medium">{e.section.course.title}</span>
              </div>
              <Badge tone="yellow">候补 #{e.waitlist_position ?? "-"}</Badge>
            </CardContent>
          </Card>
        ))}
        {!q.isLoading && !q.isError && (q.data ?? []).length === 0 && (
          <p className="text-muted-foreground">暂无候补。</p>
        )}
      </div>
    </div>
  );
}
