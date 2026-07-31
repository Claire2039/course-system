"use client";

import { type ReactNode } from "react";
import { RequireAuth } from "@/lib/auth";

export default function TeacherLayout({ children }: { children: ReactNode }) {
  return <RequireAuth role="TEACHER">{children}</RequireAuth>;
}
