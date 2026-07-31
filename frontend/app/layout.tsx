import type { Metadata } from "next";
import { Providers } from "./providers";
import { ToasterProvider } from "@/components/toaster";
import "./globals.css";

export const metadata: Metadata = {
  title: "选课系统",
  description: "学校选课系统（Next.js + FastAPI）",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>
          <ToasterProvider>{children}</ToasterProvider>
        </Providers>
      </body>
    </html>
  );
}
