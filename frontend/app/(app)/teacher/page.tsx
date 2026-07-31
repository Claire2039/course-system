"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";

export default function TeacherPage() {
  const q = useQuery({
    queryKey: ["my-sections"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/me/sections");
      if (!data) throw new Error("加载失败");
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">我的教学班</h1>
      <div className="space-y-2">
        {(q.data ?? []).map((s) => (
          <Card key={s.id}>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <span className="font-mono text-xs text-muted-foreground">{s.course.code}</span>{" "}
                <span className="font-medium">{s.course.title}</span>
                <div className="text-sm text-muted-foreground">
                  容量 {s.capacity} · 已选 {s.enrolled_count}
                </div>
              </div>
              <Link
                href={`/teacher/sections/${s.id}`}
                className="text-sm text-primary hover:underline"
              >
                管理 →
              </Link>
            </CardContent>
          </Card>
        ))}
        {(q.data ?? []).length === 0 && (
          <p className="text-muted-foreground">暂无教学班。</p>
        )}
      </div>
    </div>
  );
}
