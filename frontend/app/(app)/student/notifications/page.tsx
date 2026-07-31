"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";

const TYPE_LABEL: Record<string, string> = {
  enrolled: "选课成功",
  waitlisted: "加入候补",
  promoted: "候补转正",
  dropped: "退课",
};

export default function NotificationsPage() {
  const q = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/me/notifications");
      if (!data) throw new Error("加载失败");
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">通知</h1>
      <div className="space-y-2">
        {(q.data ?? []).map((n) => (
          <Card key={n.id}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">{TYPE_LABEL[n.type] ?? n.type}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(n.created_at).toLocaleString()}
                </span>
              </div>
              <pre className="mt-1 overflow-x-auto text-xs text-muted-foreground">
                {JSON.stringify(n.payload)}
              </pre>
            </CardContent>
          </Card>
        ))}
        {(q.data ?? []).length === 0 && (
          <p className="text-muted-foreground">暂无通知。</p>
        )}
      </div>
    </div>
  );
}
