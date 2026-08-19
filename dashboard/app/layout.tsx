import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "ACN Archaeologist · 人工审核台",
  description: "双语 Frozen HTML 与 Payload 的本地人工审核页面",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
