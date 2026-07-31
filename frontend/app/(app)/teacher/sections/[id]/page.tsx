"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "";
type Assignment = components["schemas"]["AssignmentOut"];
type RosterRow = components["schemas"]["RosterSubmissionOut"];

export default function TeacherSectionPage() {
  const params = useParams();
  const id = Number(params?.id);
  const qc = useQueryClient();

  const rosterQ = useQuery({
    queryKey: ["roster", id],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/sections/{section_id}/roster", {
        params: { path: { section_id: id } },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
    enabled: !!id,
  });
  const assignsQ = useQuery({
    queryKey: ["section-assignments", id],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/sections/{section_id}/assignments", {
        params: { path: { section_id: id } },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
    enabled: !!id,
  });

  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const createMu = useMutation({
    mutationFn: async () => {
      const { data, error } = await apiClient.POST(
        "/api/v1/sections/{section_id}/assignments",
        {
          params: { path: { section_id: id } },
          body: {
            title,
            due_at: new Date(due).toISOString(),
            allow_late: true,
            late_deadline: new Date(due).toISOString(),
          },
        }
      );
      if (error || !data) throw new Error(apiErrorMessage(error, "创建失败"));
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["section-assignments", id] });
      setTitle("");
      setDue("");
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">教学班 #{id}</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">花名册（{(rosterQ.data ?? []).length}）</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1 text-sm">
            {(rosterQ.data ?? []).map((s) => (
              <li key={s.user_id}>
                {s.student_no} · {s.name}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">作业</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Input
              className="w-48"
              placeholder="作业标题"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <Input
              className="w-56"
              type="datetime-local"
              value={due}
              onChange={(e) => setDue(e.target.value)}
            />
            <Button
              size="sm"
              disabled={!title || !due || createMu.isPending}
              onClick={() => createMu.mutate()}
            >
              布置
            </Button>
            {createMu.isError && (
              <span className="text-xs text-red-600">{(createMu.error as Error).message}</span>
            )}
          </div>

          {(assignsQ.data ?? []).map((a) => (
            <AssignmentPanel key={a.id} sectionId={id} assignment={a} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function AssignmentPanel({
  sectionId,
  assignment,
}: {
  sectionId: number;
  assignment: Assignment;
}) {
  const [open, setOpen] = useState(false);
  const subsQ = useQuery({
    queryKey: ["submissions", sectionId, assignment.id],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/sections/{section_id}/submissions", {
        params: {
          path: { section_id: sectionId },
          query: { assignment_id: assignment.id },
        },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
    enabled: open,
  });

  return (
    <div className="rounded-md border p-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-medium">{assignment.title}</span>
          <span className="ml-2 text-xs text-muted-foreground">
            截止 {new Date(assignment.due_at).toLocaleString()}
          </span>
        </div>
        <Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)}>
          {open ? "收起" : "查看提交"}
        </Button>
      </div>
      {open && (
        <div className="mt-2 space-y-2">
          {(subsQ.data ?? []).map((r) => (
            <GradeRow key={r.student_id} sectionId={sectionId} assignmentId={assignment.id} row={r} />
          ))}
          {(subsQ.data ?? []).length === 0 && (
            <p className="text-xs text-muted-foreground">暂无学生。</p>
          )}
        </div>
      )}
    </div>
  );
}

async function downloadFile(submissionId: number) {
  const res = await fetch(`${API}/api/v1/submissions/${submissionId}/file`, {
    credentials: "include",
  });
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `submission_${submissionId}`;
  a.click();
  URL.revokeObjectURL(url);
}

function GradeRow({
  sectionId,
  assignmentId,
  row,
}: {
  sectionId: number;
  assignmentId: number;
  row: RosterRow;
}) {
  const qc = useQueryClient();
  const [score, setScore] = useState(row.grade ? String(row.grade.score) : "");
  const [feedback, setFeedback] = useState(row.grade?.feedback ?? "");

  const gradeMu = useMutation({
    mutationFn: async () => {
      const sid = row.submission?.id;
      if (!sid) throw new Error("该生未提交，无法打分。");
      const { error } = await apiClient.POST("/api/v1/submissions/{submission_id}/grade", {
        params: { path: { submission_id: sid } },
        body: { score: Number(score), feedback: feedback || null },
      });
      if (error) throw new Error(apiErrorMessage(error, "打分失败"));
    },
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["submissions", sectionId, assignmentId] }),
  });

  const submitted = !!row.submission;
  return (
    <div className="flex flex-wrap items-center gap-2 border-t pt-2 text-sm">
      <span className="w-44">
        {row.student_no} · {row.student_name}
      </span>
      <span className="text-muted-foreground">
        {!submitted
          ? "未提交"
          : row.submission!.status === "LATE"
          ? "迟交"
          : "已提交"}
      </span>
      {row.submission?.has_file && (
        <button
          className="text-xs text-primary hover:underline"
          onClick={() => downloadFile(row.submission!.id)}
        >
          附件
        </button>
      )}
      <Input
        className="h-8 w-20"
        type="number"
        placeholder="分数"
        value={score}
        onChange={(e) => setScore(e.target.value)}
        disabled={!submitted}
      />
      <Input
        className="h-8 w-40"
        placeholder="评语"
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        disabled={!submitted}
      />
      <Button
        size="sm"
        disabled={!submitted || gradeMu.isPending}
        onClick={() => gradeMu.mutate()}
      >
        打分
      </Button>
      {gradeMu.isError && (
        <span className="text-xs text-red-600">{(gradeMu.error as Error).message}</span>
      )}
    </div>
  );
}
