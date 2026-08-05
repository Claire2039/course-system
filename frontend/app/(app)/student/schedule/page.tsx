"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const DAYS = [1, 2, 3, 4, 5, 6, 7];
const DAY_NAMES = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export default function SchedulePage() {
  const qc = useQueryClient();

  const enrQ = useQuery({
    queryKey: ["enrollments"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/me/enrollments");
      if (!data) throw new Error("加载失败");
      return data;
    },
  });
  const periodsQ = useQuery({
    queryKey: ["periods"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/periods");
      if (!data) throw new Error("加载失败");
      return data;
    },
  });

  const dropMu = useMutation({
    mutationFn: async (enrollmentId: number) => {
      const { error } = await apiClient.DELETE(
        "/api/v1/enrollments/{enrollment_id}",
        { params: { path: { enrollment_id: enrollmentId } } }
      );
      if (error) throw new Error(apiErrorMessage(error, "退课失败"));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["enrollments"] });
      qc.invalidateQueries({ queryKey: ["sections"] });
    },
  });

  const periods = periodsQ.data ?? [];
  const maxPeriod = periods.length > 0 ? Math.max(...periods.map((p) => p.period_no)) : 12;
  const periodRows = Array.from({ length: maxPeriod }, (_, i) => i + 1);

  const grid: Record<string, string> = {};
  for (const e of enrQ.data ?? []) {
    for (const ts of e.section.time_slots) {
      for (let p = ts.start_period; p <= ts.end_period; p++) {
        grid[`${ts.day_of_week}-${p}`] = e.section.course.code;
      }
    }
  }

  if (enrQ.isError || periodsQ.isError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">我的课表</h1>
        <Card>
          <CardContent className="p-4 text-sm text-destructive">
            课表加载失败，请刷新页面后重试。
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">我的课表</h1>
      <Card>
        <CardContent className="overflow-x-auto p-4">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="border p-2 text-muted-foreground">节</th>
                {DAYS.map((d) => (
                  <th key={d} className="border p-2">
                    {DAY_NAMES[d]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {periodRows.map((p) => (
                <tr key={p}>
                  <td className="border p-2 text-center text-muted-foreground">{p}</td>
                  {DAYS.map((d) => {
                    const code = grid[`${d}-${p}`];
                    return (
                      <td key={d} className="border p-2 text-center">
                        {code ? (
                          <span className="rounded bg-primary/10 px-2 py-1 font-mono text-xs">
                            {code}
                          </span>
                        ) : null}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">已选课程（可退课）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(enrQ.data ?? []).map((e) => (
            <div
              key={e.id}
              className="flex items-center justify-between rounded border p-3"
            >
              <div>
                <span className="font-mono text-xs text-muted-foreground">
                  {e.section.course.code}
                </span>{" "}
                <span className="font-medium">{e.section.course.title}</span>
              </div>
              <Button
                size="sm"
                variant="outline"
                disabled={dropMu.isPending}
                onClick={() => dropMu.mutate(e.id)}
              >
                退课
              </Button>
            </div>
          ))}
          {(enrQ.data ?? []).length === 0 && (
            <p className="text-sm text-muted-foreground">暂无已选课程。</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
