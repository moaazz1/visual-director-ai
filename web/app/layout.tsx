import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Visual Director AI",
  description: "Creative review and production direction for advertising imagery.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
