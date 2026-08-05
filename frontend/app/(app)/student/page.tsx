"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { CATEGORY_ORDER, CATEGORY_TONE } from "@/lib/categories";

function chip(active: boolean) {
  return `rounded-full border px-3 py-1 text-xs transition ${
    active
      ? "border-primary bg-primary text-primary-foreground"
      : "border-border text-muted-foreground hover:bg-accent"
  }`;
}

export default function CatalogPage() {
  const [query, setQuery] = useState("");
  const [cat, setCat] = useState<string>("");

  const coursesQ = useQuery({
    queryKey: ["courses"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/v1/courses", {
        params: { query: { limit: 100 } },
      });
      if (!data) throw new Error("加载失败");
      return data;
    },
  });

  const all = coursesQ.data?.items ?? [];
  const filtered = all.filter((c) => {
    if (cat && c.category !== cat) return false;
    if (query) {
      const q = query.toLowerCase();
      const hay = `${c.code} ${c.title} ${c.department ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const groups = useMemo(() => {
    const m = new Map<string, typeof filtered>();
    for (const c of filtered) {
      const arr = m.get(c.category) ?? [];
      arr.push(c);
      m.set(c.category, arr);
    }
    return CATEGORY_ORDER.filter((k) => m.has(k)).map(
      (k) => [k, m.get(k)!] as const
    );
  }, [filtered]);

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索课程代码 / 名称 / 专业…"
          className="max-w-md"
        />
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setCat("")} className={chip(cat === "")}>
            全部
          </button>
          {CATEGORY_ORDER.map((k) => (
            <button
              key={k}
              onClick={() => setCat(k)}
              className={chip(cat === k)}
            >
              {k}
            </button>
          ))}
        </div>
      </div>

      {coursesQ.isLoading && (
        <p className="text-muted-foreground">加载中…</p>
      )}
      {coursesQ.isError && (
        <p className="text-destructive">课程加载失败，请刷新重试。</p>
      )}

      {groups.map(([category, items]) => (
        <section key={category} className="space-y-3">
          <div className="flex items-center gap-2">
            <Badge tone={CATEGORY_TONE[category] ?? "default"}>{category}</Badge>
            <span className="text-sm text-muted-foreground">{items.length} 门</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((c) => (
              <Link key={c.id} href={`/courses/${c.id}`} className="block">
                <Card className="h-full overflow-hidden transition hover:shadow-md">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={c.cover_url ?? ""}
                    alt={c.title}
                    className="h-32 w-full object-cover"
                  />
                  <CardContent className="space-y-1 p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-muted-foreground">
                        {c.code}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {c.credits} 学分
                      </span>
                    </div>
                    <div className="font-medium leading-snug">{c.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {c.department}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      ))}

      {!coursesQ.isLoading && !coursesQ.isError && groups.length === 0 && (
        <p className="text-muted-foreground">无匹配课程。</p>
      )}
    </div>
  );
}
