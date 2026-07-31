"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";

export function useUser() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/auth/me");
      if (error || !data) throw new Error("unauthenticated");
      return data;
    },
    retry: false,
  });
}

export function useLogout() {
  const router = useRouter();
  const qc = useQueryClient();
  return async () => {
    await apiClient.POST("/api/v1/auth/logout", {});
    qc.resetQueries({ queryKey: ["me"] });
    router.replace("/login");
  };
}

export function RequireAuth({
  role,
  children,
}: {
  role: "STUDENT" | "TEACHER" | "ADMIN";
  children: ReactNode;
}) {
  const { data: user, isLoading, isError } = useUser();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (isError || !user) {
      router.replace("/login");
      return;
    }
    if (user.must_change_password) {
      router.replace("/login/change-password");
    }
  }, [isLoading, isError, user, router]);

  if (isLoading) return <div className="p-8 text-muted-foreground">加载中…</div>;
  if (isError || !user) return null;
  if (user.must_change_password) return null;
  if (user.role !== role) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16 text-muted-foreground">
        该账号角色（{user.role}）的前端尚在开发中（M7）。
      </main>
    );
  }
  return <>{children}</>;
}
