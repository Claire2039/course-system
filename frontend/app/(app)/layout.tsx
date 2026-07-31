"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { useLogout, useUser } from "@/lib/auth";
import { useEventStream } from "@/lib/eventstream";

const NAVS: Record<string, { href: string; label: string }[]> = {
  STUDENT: [
    { href: "/student", label: "课程目录" },
    { href: "/student/schedule", label: "我的课表" },
    { href: "/student/waitlist", label: "我的候补" },
    { href: "/student/assignments", label: "我的作业" },
    { href: "/student/notifications", label: "通知" },
  ],
  TEACHER: [{ href: "/teacher", label: "我的教学班" }],
  ADMIN: [{ href: "/admin", label: "目录管理" }],
};

export default function AppLayout({ children }: { children: ReactNode }) {
  const { data: user } = useUser();
  const logout = useLogout();
  useEventStream(!!user);
  const nav = (user && NAVS[user.role]) ?? [];

  return (
    <div className="min-h-screen">
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <nav className="flex gap-5 text-sm font-medium">
            {nav.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="text-muted-foreground hover:text-foreground"
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <button
            onClick={() => logout()}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            退出
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
