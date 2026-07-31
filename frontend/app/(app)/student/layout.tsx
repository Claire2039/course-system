"use client";

import { type ReactNode } from "react";
import { RequireAuth } from "@/lib/auth";

export default function StudentLayout({ children }: { children: ReactNode }) {
  return <RequireAuth role="STUDENT">{children}</RequireAuth>;
}
