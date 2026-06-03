import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/AppShell";
import { TourProvider } from "@/components/TourProvider";
import { TourOverlay } from "@/components/TourOverlay";

export const metadata: Metadata = {
  title: "horus-os",
  description:
    "Self-hosted autonomous AI command center. Open source, local first.",
  icons: {
    icon: "/horus-eye.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#0a0b0f",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <TourProvider>
            <AppShell>{children}</AppShell>
            <TourOverlay />
          </TourProvider>
        </Providers>
      </body>
    </html>
  );
}
