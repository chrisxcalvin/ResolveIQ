import type { Metadata } from "next";
import { Archivo, IBM_Plex_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppHeader } from "@/components/app-header";
import "./globals.css";

// Archivo: UI text, labels, body — a grotesk sans with real character,
// deliberately not the default system-ui/Inter look.
const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
});

// IBM Plex Mono: reserved for DATA values only (ids, timestamps, scores,
// confidence) — not decoration. A monospace face used specifically where
// numbers need to be scannable, which is the point, not a generic
// monospace-for-labels tic.
const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "ResolveIQ",
  description: "AI-assisted support ticket triage",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${ibmPlexMono.variable} dark h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <TooltipProvider delay={200}>
          <AppHeader />
          {children}
        </TooltipProvider>
      </body>
    </html>
  );
}
