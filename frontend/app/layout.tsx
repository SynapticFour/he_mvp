// SPDX-License-Identifier: Apache-2.0
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { EmailProvider } from "@/lib/email-context";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-geist-sans" });

export const metadata: Metadata = {
  title: "SecureCollab – Encrypted Clinical Data Analysis",
  description:
    "Collaborate on sensitive clinical data without ever exposing it. Secure B2B platform for pharma.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen font-sans antialiased">
        <EmailProvider>{children}</EmailProvider>
      </body>
    </html>
  );
}
