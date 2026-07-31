"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@/lib/auth";

/** 根路径：按登录状态跳转（未登录→/login，学生→/student，其余→占位）。 */
export default function Home() {
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
      return;
    }
    router.replace("/student");
  }, [isLoading, isError, user, router]);

  return <div className="p-8 text-muted-foreground">跳转中…</div>;
}
