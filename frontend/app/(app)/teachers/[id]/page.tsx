"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_TONE } from "@/lib/categories";

export default function TeacherDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const teacherQ = useQuery({
    queryKey: ["teacher", id],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/teachers/{teacher_id}", {
        params: { path: { teacher_id: id } },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
    enabled: Number.isFinite(id),
  });
  const sectionsQ = useQuery({
    queryKey: ["sections", "all"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/sections", {
        params: { query: { limit: 100 } },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
  });
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

  const t = teacherQ.data;
  if (teacherQ.isLoading)
    return <p className="text-muted-foreground">加载中…</p>;
  if (teacherQ.isError || !t)
    return (
      <div className="space-y-3">
        <Link href="/student" className="text-sm text-muted-foreground hover:text-foreground">
          ← 返回
        </Link>
        <p className="text-destructive">教师信息加载失败，请返回重试。</p>
      </div>
    );

  // 该教师所开设的课程：通过 teacher_no 在 sections 中匹配，再用 code 关联到 courses
  const myCodes = new Set(
    (sectionsQ.data?.items ?? [])
      .filter((s) => s.teacher.teacher_no === t.teacher_no)
      .map((s) => s.course.code)
  );
  const myCourses = (coursesQ.data?.items ?? []).filter((c) =>
    myCodes.has(c.code)
  );
  const education = t.education ?? [];
  const publications = t.publications ?? [];

  return (
    <div className="space-y-6">
      <Link href="/student" className="text-sm text-muted-foreground hover:text-foreground">
        ← 返回目录
      </Link>

      <Card>
        <CardContent className="space-y-3 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">{t.name}</h1>
            <Badge tone="blue">{t.title}</Badge>
            <span className="text-sm text-muted-foreground">{t.department}</span>
          </div>
          {t.bio && <p className="text-muted-foreground">{t.bio}</p>}
          {t.research_interests && (
            <p className="text-sm">
              <span className="text-muted-foreground">研究方向：</span>
              {t.research_interests}
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">教育经历</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {education.length > 0 ? (
              education.map((e, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span>
                    <span className="font-medium">{e.degree}</span>
                    <span className="text-muted-foreground"> · {e.institution}</span>
                  </span>
                  <span className="text-muted-foreground">{e.year}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">暂无信息。</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">文献成果</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {publications.length > 0 ? (
              publications.map((p, i) => (
                <div key={i} className="text-sm">
                  <div>{p.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.venue} · {p.year}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">暂无信息。</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">开设课程</CardTitle>
        </CardHeader>
        <CardContent>
          {myCourses.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {myCourses.map((c) => (
                <Link key={c.id} href={`/courses/${c.id}`} className="block">
                  <div className="overflow-hidden rounded-lg border transition hover:shadow-md">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={c.cover_url ?? ""}
                      alt={c.title}
                      className="h-28 w-full object-cover"
                    />
                    <div className="space-y-1 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs text-muted-foreground">
                          {c.code}
                        </span>
                        <Badge tone={CATEGORY_TONE[c.category] ?? "default"}>
                          {c.category}
                        </Badge>
                      </div>
                      <div className="text-sm font-medium leading-snug">
                        {c.title}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">本学期暂无开设课程。</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
