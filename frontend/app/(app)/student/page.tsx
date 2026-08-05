"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { useToast } from "@/components/toaster";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

export default function CatalogPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [selected, setSelected] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [dept, setDept] = useState("");

  const coursesQ = useQuery({
    queryKey: ["courses"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/courses", {
        params: { query: { limit: 100 } },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
  });

  const sectionsQ = useQuery({
    queryKey: ["sections", "course", selected],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/sections", {
        params: { query: { course_id: selected!, limit: 100 } },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
    enabled: selected !== null,
  });

  const enrQ = useQuery({
    queryKey: ["enrollments"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/me/enrollments");
      if (!data) throw new Error("加载失败");
      return data;
    },
  });

  const enrollMu = useMutation({
    mutationFn: async (sectionId: number) => {
      const { data, error } = await apiClient.POST(
        "/api/v1/sections/{section_id}/enroll",
        { params: { path: { section_id: sectionId } } }
      );
      if (error || !data) throw new Error(apiErrorMessage(error, "选课失败"));
      return data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["enrollments"] });
      qc.invalidateQueries({ queryKey: ["sections"] });
      qc.invalidateQueries({ queryKey: ["waitlist"] });
      toast(
        data.status === "ENROLLED"
          ? "选课成功 ✓"
          : `已加入候补，位次 ${data.position ?? "-"}`,
        data.status === "ENROLLED" ? "success" : "info"
      );
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const allCourses = coursesQ.data?.items ?? [];
  const departments = useMemo(
    () => [...new Set(allCourses.map((c) => c.department))].sort(),
    [allCourses]
  );
  const filtered = allCourses.filter((c) => {
    if (dept && c.department !== dept) return false;
    if (query) {
      const q = query.toLowerCase();
      if (
        !c.code.toLowerCase().includes(q) &&
        !c.title.toLowerCase().includes(q)
      )
        return false;
    }
    return true;
  });

  const enrolledIds = new Set((enrQ.data ?? []).map((e) => e.section_id));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">课程目录</h1>
      <div className="grid gap-6 md:grid-cols-[300px_1fr]">
        <Card>
          <CardHeader className="space-y-2">
            <CardTitle className="text-base">课程</CardTitle>
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索代码 / 名称…"
              className="h-8 text-sm"
            />
            <select
              value={dept}
              onChange={(e) => setDept(e.target.value)}
              className="h-8 rounded-md border border-input bg-background px-2 text-sm"
            >
              <option value="">全部专业</option>
              {departments.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </CardHeader>
          <CardContent className="space-y-1">
            {filtered.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelected(c.id)}
                className={`block w-full rounded px-2 py-1.5 text-left text-sm ${
                  selected === c.id ? "bg-accent" : "hover:bg-accent/50"
                }`}
              >
                <span className="font-mono text-xs text-muted-foreground">{c.code}</span>
                <div>{c.title}</div>
              </button>
            ))}
            {coursesQ.isLoading && (
              <p className="px-2 py-1 text-sm text-muted-foreground">加载中…</p>
            )}
            {coursesQ.isError && (
              <p className="px-2 py-1 text-sm text-destructive">
                课程加载失败，请刷新重试。
              </p>
            )}
            {!coursesQ.isLoading && !coursesQ.isError && filtered.length === 0 && (
              <p className="px-2 py-1 text-sm text-muted-foreground">无匹配课程。</p>
            )}
          </CardContent>
        </Card>

        <div className="space-y-3">
          {selected === null && (
            <p className="text-muted-foreground">← 选择左侧课程查看教学班</p>
          )}
          {sectionsQ.isError && (
            <p className="text-sm text-destructive">教学班加载失败，请刷新重试。</p>
          )}
          {(sectionsQ.data?.items ?? []).map((s) => {
            const enrolled = enrolledIds.has(s.id);
            const full = s.available <= 0;
            return (
              <Card key={s.id}>
                <CardContent className="flex items-start justify-between gap-4 p-4">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{s.course.title}</span>
                      <span className="text-xs text-muted-foreground">{s.course.credits} 学分</span>
                      <Badge tone={full ? "red" : "green"}>
                        余 {s.available}/{s.capacity}
                      </Badge>
                      {enrolled && <Badge tone="default">已选</Badge>}
                    </div>
                    {s.course.description && (
                      <p className="text-sm text-muted-foreground">{s.course.description}</p>
                    )}
                    <div className="text-sm">
                      <span className="text-foreground">主讲：{s.teacher.name}</span>
                      <span className="text-muted-foreground"> · {s.room} ·{" "}
                        {s.time_slots
                          .map((t) => `周${t.day_of_week} 第${t.start_period}-${t.end_period}节`)
                          .join("，")}
                      </span>
                    </div>
                    {s.teacher.bio && (
                      <p className="text-xs text-muted-foreground">教师简介：{s.teacher.bio}</p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant={full ? "outline" : "default"}
                    disabled={enrolled || enrollMu.isPending}
                    onClick={() => enrollMu.mutate(s.id)}
                  >
                    {enrolled ? "已选" : full ? "排队候补" : "选课"}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
