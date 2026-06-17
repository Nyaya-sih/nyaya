import type { Metadata } from "next";
import { Manrope, Cormorant_Garamond, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/providers/query-provider";
import { ThemeProvider } from "@/providers/theme-provider";
import { Navbar } from "@/components/layout/navbar";
import { Footer } from "@/components/layout/footer";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
});

const cormorant = Cormorant_Garamond({
  variable: "--font-cormorant",
  weight: ["500", "600", "700"],
  subsets: ["latin"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NyayaAI — Litigation Intelligence Workspace",
  description: "Legal research workspace for Indian courts with retrieval, assistant, courtroom and tendency insights",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="light">
      <body className={`${manrope.variable} ${cormorant.variable} ${jetbrains.variable} antialiased`}>
        <QueryProvider>
          <ThemeProvider>
            <div className="min-h-screen bg-legal-gradient">
              <div className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(circle_at_12%_10%,rgba(249,118,18,0.08),transparent_28%),radial-gradient(circle_at_86%_9%,rgba(49,101,128,0.14),transparent_28%)]" />
              <Navbar />
              <main className="relative z-10">{children}</main>
              <Footer />
            </div>
          </ThemeProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
