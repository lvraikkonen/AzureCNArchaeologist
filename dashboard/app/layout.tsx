import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("http://localhost:3000"),
  title: "Azure 中国区产品能力追踪",
  description:
    "105 个 Azure 中国区产品入口的机器证据、人工内容检查与证据绑定状态。",
  applicationName: "Azure CN Capability Dashboard",
  openGraph: {
    type: "website",
    locale: "zh_CN",
    title: "Azure 中国区 · 产品能力追踪",
    description: "105 个产品入口 · v0.4 Step 3 · 本地只读证据投影",
    images: [
      {
        url: "/og.png",
        width: 1731,
        height: 909,
        alt: "Azure 中国区产品能力追踪 Dashboard",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Azure 中国区 · 产品能力追踪",
    description: "105 个产品入口 · v0.4 Step 3 · 本地只读证据投影",
    images: ["/og.png"],
  },
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#f6f8fb",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
