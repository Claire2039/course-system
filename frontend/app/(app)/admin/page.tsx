"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "";
type Tab = "courses" | "sections" | "semesters" | "import";

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("courses");
  const tabs: { key: Tab; label: string }[] = [
    { key: "courses", label: "课程" },
    { key: "sections", label: "教学班" },
    { key: "semesters", label: "学期" },
    { key: "import", label: "导入用户" },
  ];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">目录管理</h1>
      <div className="flex gap-2 border-b">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              tab === t.key
                ? "border-primary font-medium"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "courses" && <CoursesPanel />}
      {tab === "sections" && <SectionsPanel />}
      {tab === "semesters" && <SemestersPanel />}
      {tab === "import" && <ImportPanel />}
    </div>
  );
}

function CoursesPanel() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["courses"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/courses", {
        params: { query: { limit: 100 } },
      });
      if (!data) throw new Error("fail");
      return data;
    },
  });
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [credits, setCredits] = useState("3");
  const [dept, setDept] = useState("CS");
  const createMu = useMutation({
    mutationFn: async () => {
      const { error } = await apiClient.POST("/api/v1/admin/courses", {
        body: { code, title, credits: Number(credits), department: dept },
      });
      if (error) throw new Error(apiErrorMessage(error, "创建失败"));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["courses"] });
      setCode(""); setTitle("");
    },
  });
  const delMu = useMutation({
    mutationFn: async (id: number) => {
      const { error } = await apiClient.DELETE("/api/v1/admin/courses/{course_id}", {
        params: { path: { course_id: id } },
      });
      if (error) throw new Error(apiErrorMessage(error, "删除失败"));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["courses"] }),
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">课程</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Input className="w-32" placeholder="代码" value={code} onChange={(e) => setCode(e.target.value)} />
          <Input className="w-48" placeholder="名称" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input className="w-20" type="number" value={credits} onChange={(e) => setCredits(e.target.value)} />
          <Input className="w-28" value={dept} onChange={(e) => setDept(e.target.value)} />
          <Button size="sm" disabled={!code || !title || createMu.isPending} onClick={() => createMu.mutate()}>新建</Button>
          {createMu.isError && <span className="text-xs text-red-600">{(createMu.error as Error).message}</span>}
        </div>
        <table className="w-full text-sm">
          <tbody>
            {(q.data?.items ?? []).map((c) => (
              <tr key={c.id} className="border-t">
                <td className="py-1 font-mono text-xs">{c.code}</td>
                <td className="py-1">{c.title}</td>
                <td className="py-1 text-muted-foreground">{c.credits} 学分 · {c.department}</td>
                <td className="py-1 text-right">
                  <button className="text-xs text-red-600 hover:underline" onClick={() => delMu.mutate(c.id)}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function SectionsPanel() {
  const qc = useQueryClient();
  const sectionsQ = useQuery({
    queryKey: ["sections", "admin"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/sections", { params: { query: { limit: 100 } } });
      if (!data) throw new Error("fail");
      return data;
    },
  });
  const coursesQ = useQuery({
    queryKey: ["courses"],
    queryFn: async () => (await apiClient.GET("/api/v1/courses", { params: { query: { limit: 200 } } })).data,
  });
  const teachersQ = useQuery({
    queryKey: ["admin-teachers"],
    queryFn: async () => (await apiClient.GET("/api/v1/admin/teachers")).data,
  });
  const semsQ = useQuery({
    queryKey: ["admin-semesters"],
    queryFn: async () => (await apiClient.GET("/api/v1/admin/semesters")).data,
  });
  const [courseId, setCourseId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [semesterId, setSemesterId] = useState("");
  const [capacity, setCapacity] = useState("50");
  const [room, setRoom] = useState("R1");
  const createMu = useMutation({
    mutationFn: async () => {
      const { error } = await apiClient.POST("/api/v1/admin/sections", {
        body: {
          course_id: Number(courseId),
          teacher_id: Number(teacherId),
          semester_id: Number(semesterId),
          capacity: Number(capacity),
          room,
        },
      });
      if (error) throw new Error(apiErrorMessage(error, "创建失败"));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sections", "admin"] }),
  });
  const delMu = useMutation({
    mutationFn: async (id: number) => {
      const { error } = await apiClient.DELETE("/api/v1/admin/sections/{section_id}", {
        params: { path: { section_id: id } },
      });
      if (error) throw new Error(apiErrorMessage(error, "删除失败"));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sections", "admin"] }),
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">教学班</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <select className="h-9 rounded-md border px-2" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
            <option value="">课程…</option>
            {(coursesQ.data?.items ?? []).map((c) => <option key={c.id} value={c.id}>{c.code} {c.title}</option>)}
          </select>
          <select className="h-9 rounded-md border px-2" value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
            <option value="">教师…</option>
            {(teachersQ.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name} ({t.teacher_no})</option>)}
          </select>
          <select className="h-9 rounded-md border px-2" value={semesterId} onChange={(e) => setSemesterId(e.target.value)}>
            <option value="">学期…</option>
            {(semsQ.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}{s.is_current ? " · 当前" : ""}</option>)}
          </select>
          <Input className="w-20" type="number" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
          <Input className="w-24" value={room} onChange={(e) => setRoom(e.target.value)} />
          <Button size="sm" disabled={!courseId || !teacherId || !semesterId || createMu.isPending} onClick={() => createMu.mutate()}>新建</Button>
          {createMu.isError && <span className="text-xs text-red-600">{(createMu.error as Error).message}</span>}
        </div>
        <table className="w-full text-sm">
          <tbody>
            {(sectionsQ.data?.items ?? []).map((s) => (
              <tr key={s.id} className="border-t">
                <td className="py-1 font-mono text-xs">{s.course.code}</td>
                <td className="py-1">{s.teacher.name}</td>
                <td className="py-1 text-muted-foreground">{s.seats_taken}/{s.capacity} · {s.room}</td>
                <td className="py-1 text-right">
                  <button className="text-xs text-red-600 hover:underline" onClick={() => delMu.mutate(s.id)}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function SemestersPanel() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["admin-semesters"],
    queryFn: async () => (await apiClient.GET("/api/v1/admin/semesters")).data,
  });
  const [name, setName] = useState("");
  const [open, setOpen] = useState("");
  const [close, setClose] = useState("");
  const createMu = useMutation({
    mutationFn: async () => {
      const { error } = await apiClient.POST("/api/v1/admin/semesters", {
        body: {
          name,
          is_current: true,
          enroll_open_at: new Date(open).toISOString(),
          enroll_close_at: new Date(close).toISOString(),
          drop_deadline: new Date(close).toISOString(),
          max_credits: 30,
          max_courses: 8,
        },
      });
      if (error) throw new Error(apiErrorMessage(error, "创建失败"));
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-semesters"] }); setName(""); setOpen(""); setClose(""); },
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">学期</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Input className="w-40" placeholder="名称" value={name} onChange={(e) => setName(e.target.value)} />
          <Input className="w-44" type="datetime-local" value={open} onChange={(e) => setOpen(e.target.value)} />
          <Input className="w-44" type="datetime-local" value={close} onChange={(e) => setClose(e.target.value)} />
          <Button size="sm" disabled={!name || !open || !close || createMu.isPending} onClick={() => createMu.mutate()}>新建（设为当前）</Button>
        </div>
        <table className="w-full text-sm">
          <tbody>
            {(q.data ?? []).map((s) => (
              <tr key={s.id} className="border-t">
                <td className="py-1">{s.name}</td>
                <td className="py-1 text-muted-foreground">选课 {new Date(s.enroll_open_at).toLocaleDateString()} ~ {new Date(s.enroll_close_at).toLocaleDateString()}</td>
                <td className="py-1">{s.is_current ? "当前" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function ImportPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<{ imported: number; users: { email: string; initial_password: string }[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onUpload() {
    if (!file) return;
    setBusy(true); setError(null); setResult(null);
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API}/api/v1/admin/import-users`, { method: "POST", credentials: "include", body: fd });
    setBusy(false);
    const j = await res.json().catch(() => null);
    if (!res.ok) {
      setError(j?.detail?.message ?? (j?.detail ? `第 ${j.detail.errors?.[0]?.row} 行: ${j.detail.errors?.[0]?.message}` : "导入失败"));
      return;
    }
    setResult({ imported: j.imported, users: (j.users ?? []).map((u: { email: string; initial_password: string }) => ({ email: u.email, initial_password: u.initial_password })) });
  }

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">批量导入用户（CSV）</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          表头需含 role,name,email；学生需 student_no/grade/major，教师需 teacher_no/department/title。
        </p>
        <div className="flex items-center gap-2">
          <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
          <Button size="sm" disabled={!file || busy} onClick={onUpload}>上传</Button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {result && (
          <div className="space-y-1">
            <p className="text-sm">导入 {result.imported} 个用户，初始口令（仅此一次）：</p>
            <table className="w-full text-xs">
              <tbody>
                {result.users.map((u) => (
                  <tr key={u.email} className="border-t">
                    <td className="py-1">{u.email}</td>
                    <td className="py-1 font-mono">{u.initial_password}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
