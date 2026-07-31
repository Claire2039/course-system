"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { RequireAuth, useLogout } from "@/lib/auth";
import { useEventStream } from "@/lib/eventstream";

const NAV = [
  { href: "/student", label: "课程目录" },
  { href: "/student/schedule", label: "我的课表" },
  { href: "/student/waitlist", label: "我的候补" },
  { href: "/student/assignments", label: "我的作业" },
  { href: "/student/notifications", label: "通知" },
];

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth role="STUDENT">
      <Shell>{children}</Shell>
    </RequireAuth>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const logout = useLogout();
  useEventStream(true);
  return (
    <div className="min-h-screen">
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <nav className="flex gap-5 text-sm font-medium">
            {NAV.map((n) => (
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
