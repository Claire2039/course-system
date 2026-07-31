"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { roleHome, useUser } from "@/lib/auth";

/** 根路径：按登录状态/角色跳转。 */
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
    router.replace(roleHome(user.role));
  }, [isLoading, isError, user, router]);

  return <div className="p-8 text-muted-foreground">跳转中…</div>;
}

