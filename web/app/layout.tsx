import type { Metadata } from "next";
import "./globals.css";
import { Nav, SafetyFooter } from "@/components/Chrome";
import { VoiceProvider } from "@/lib/voice";

export const metadata: Metadata = { title: "Apprentice", description: "Capture, map and teach expert care-documentation judgment" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <VoiceProvider>
          <Nav />
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-4">{children}</main>
        </VoiceProvider>
        <SafetyFooter />
      </body>
    </html>
  );
}
