"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { useToast } from "@/components/toaster";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_TONE } from "@/lib/categories";

export default function CourseDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const qc = useQueryClient();
  const { toast } = useToast();

  const courseQ = useQuery({
    queryKey: ["course", id],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/courses/{course_id}", {
        params: { path: { course_id: id } },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
    enabled: Number.isFinite(id),
  });
  const sectionsQ = useQuery({
    queryKey: ["sections", "course", id],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/sections", {
        params: { query: { course_id: id, limit: 100 } },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
    enabled: Number.isFinite(id),
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

  const c = courseQ.data;
  const enrolledIds = new Set((enrQ.data ?? []).map((e) => e.section_id));

  if (courseQ.isLoading)
    return <p className="text-muted-foreground">加载中…</p>;
  if (courseQ.isError || !c)
    return (
      <div className="space-y-3">
        <Link href="/student" className="text-sm text-muted-foreground hover:text-foreground">
          ← 返回目录
        </Link>
        <p className="text-destructive">课程加载失败，请返回重试。</p>
      </div>
    );

  const sections = sectionsQ.data?.items ?? [];

  return (
    <div className="space-y-6">
      <Link href="/student" className="text-sm text-muted-foreground hover:text-foreground">
        ← 返回目录
      </Link>

      <Card className="overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={c.cover_url ?? ""}
          alt={c.title}
          className="h-48 w-full object-cover"
        />
        <CardContent className="space-y-3 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm text-muted-foreground">{c.code}</span>
            <Badge tone={CATEGORY_TONE[c.category] ?? "default"}>{c.category}</Badge>
            <span className="text-sm text-muted-foreground">
              {c.credits} 学分 · {c.department}
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">{c.title}</h1>
          {c.description && <p className="text-muted-foreground">{c.description}</p>}
          {c.prerequisites && c.prerequisites.length > 0 && (
            <p className="text-sm">
              <span className="text-muted-foreground">先修课：</span>
              {c.prerequisites.map((p) => `${p.code} ${p.title}`).join("；")}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">教学进度（教学进度表）</CardTitle>
        </CardHeader>
        <CardContent>
          {c.syllabus && c.syllabus.length > 0 ? (
            <table className="w-full text-sm">
              <tbody>
                {c.syllabus.map((s) => (
                  <tr key={s.week} className="border-b last:border-0">
                    <td className="w-20 py-2 align-top text-muted-foreground">
                      第 {s.week} 周
                    </td>
                    <td className="py-2">
                      {s.title}
                      {s.detail ? (
                        <span className="text-muted-foreground"> — {s.detail}</span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">暂无教学进度。</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">教学班（可选课）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {sectionsQ.isLoading && (
            <p className="text-sm text-muted-foreground">加载中…</p>
          )}
          {sectionsQ.isError && (
            <p className="text-sm text-destructive">教学班加载失败，请刷新。</p>
          )}
          {sections.map((s) => {
            const enrolled = enrolledIds.has(s.id);
            const full = s.available <= 0;
            return (
              <div
                key={s.id}
                className="flex items-start justify-between gap-4 rounded border p-3"
              >
                <div className="space-y-1 text-sm">
                  <div>
                    <span className="text-muted-foreground">主讲：</span>
                    <Link
                      href={`/teachers/${s.teacher.id}`}
                      className="font-medium hover:underline"
                    >
                      {s.teacher.name}
                    </Link>
                    <span className="text-muted-foreground"> · {s.room}</span>
                  </div>
                  <div className="text-muted-foreground">
                    {s.time_slots
                      .map(
                        (t) =>
                          `周${t.day_of_week} 第${t.start_period}-${t.end_period}节`
                      )
                      .join("，")}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={full ? "red" : "green"}>
                      余 {s.available}/{s.capacity}
                    </Badge>
                    {enrolled && <Badge tone="default">已选</Badge>}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant={full ? "outline" : "default"}
                  disabled={enrolled || enrollMu.isPending}
                  onClick={() => enrollMu.mutate(s.id)}
                >
                  {enrolled ? "已选" : full ? "排队候补" : "选课"}
                </Button>
              </div>
            );
          })}
          {!sectionsQ.isLoading && sections.length === 0 && (
            <p className="text-sm text-muted-foreground">本学期暂无教学班。</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
