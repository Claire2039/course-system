"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api/client";
import { useToast } from "@/components/toaster";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "";

type MyAssignment = components["schemas"]["MyAssignmentOut"];

export default function AssignmentsPage() {
  const q = useQuery({
    queryKey: ["assignments"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/me/assignments");
      if (!data) throw new Error("加载失败");
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">我的作业</h1>
      <div className="space-y-3">
        {q.isLoading && <p className="text-muted-foreground">加载中…</p>}
        {q.isError && (
          <p className="text-destructive">作业加载失败，请刷新重试。</p>
        )}
        {(q.data ?? []).map((item) => (
          <AssignmentCard key={item.assignment.id} item={item} />
        ))}
        {!q.isLoading && !q.isError && (q.data ?? []).length === 0 && (
          <p className="text-muted-foreground">暂无作业。</p>
        )}
      </div>
    </div>
  );
}

function AssignmentCard({ item }: { item: MyAssignment }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const a = item.assignment;
  const sub = item.submission;
  const grade = item.grade;

  const submitMu = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      if (file) fd.append("file", file);
      fd.append("text_comment", text);
      const res = await fetch(`${API}/api/v1/assignments/${a.id}/submit`, {
        method: "POST",
        credentials: "include",
        body: fd,
      });
      if (!res.ok) {
        const j = (await res.json().catch(() => null)) as {
          detail?: { message?: string };
        } | null;
        throw new Error(j?.detail?.message ?? "提交失败");
      }
      return res.json();
    },
    onSuccess: () => {
      toast("作业已提交 ✓", "success");
      setFile(null);
      setText("");
      qc.invalidateQueries({ queryKey: ["assignments"] });
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  async function download() {
    if (!sub) return;
    const res = await fetch(`${API}/api/v1/submissions/${sub.id}/file`, {
      credentials: "include",
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `submission_${sub.id}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const statusBadge = grade ? (
    <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-300">
      已出分 {grade.score}
    </span>
  ) : sub ? (
    <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
      {sub.status === "LATE" ? "迟交" : "已提交"}
    </span>
  ) : (
    <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 dark:bg-red-950 dark:text-red-300">
      未提交
    </span>
  );

  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <span className="font-medium">{a.title}</span>
            <span className="ml-2 text-xs text-muted-foreground">
              截止 {new Date(a.due_at).toLocaleString()}
            </span>
          </div>
          {statusBadge}
        </div>
        {a.description && (
          <p className="text-sm text-muted-foreground">{a.description}</p>
        )}
        {grade?.feedback && (
          <p className="text-sm">评语：{grade.feedback}</p>
        )}
        {sub?.text_comment && (
          <p className="text-xs text-muted-foreground">我的附言：{sub.text_comment}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="附言（可选）"
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          />
          <Button size="sm" disabled={submitMu.isPending} onClick={() => submitMu.mutate()}>
            {sub ? "重新提交" : "提交"}
          </Button>
          {sub?.has_file && (
            <Button size="sm" variant="outline" onClick={download}>
              下载我的附件
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
