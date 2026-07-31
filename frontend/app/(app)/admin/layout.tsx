"use client";

import { type ReactNode } from "react";
import { RequireAuth } from "@/lib/auth";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <RequireAuth role="ADMIN">{children}</RequireAuth>;
}
