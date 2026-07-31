"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";

type Tone = "info" | "success" | "error";
type ToastItem = { id: number; message: string; tone: Tone };

const ToastCtx = createContext<{ toast: (message: string, tone?: Tone) => void }>({
  toast: () => {},
});

export function useToast() {
  return useContext(ToastCtx);
}

const colors: Record<Tone, string> = {
  info: "bg-primary text-primary-foreground",
  success: "bg-green-600 text-white",
  error: "bg-red-600 text-white",
};

export function ToasterProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, tone: Tone = "info") => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setItems((s) => [...s, { id, message, tone }]);
    setTimeout(() => setItems((s) => s.filter((x) => x.id !== id)), 4000);
  }, []);

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className={cn("rounded-md px-4 py-2 text-sm shadow-md", colors[t.tone])}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
