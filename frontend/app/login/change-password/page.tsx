"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ChangePasswordPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { data, error: err } = await apiClient.POST(
      "/api/v1/auth/change-password",
      { body: { old_password: oldPwd, new_password: newPwd } }
    );
    setLoading(false);
    if (err || !data) {
      setError(apiErrorMessage(err, "修改失败。"));
      return;
    }
    await qc.invalidateQueries({ queryKey: ["me"] });
    router.replace("/student");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 py-12">
      <Card>
        <CardHeader>
          <CardTitle>首次登录 · 修改口令</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">旧口令</label>
              <Input
                type="password"
                value={oldPwd}
                onChange={(e) => setOldPwd(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">新口令（≥8 位）</label>
              <Input
                type="password"
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "提交中…" : "修改并继续"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
