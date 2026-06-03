import type { Metadata, Viewport } from "next";
import "./globals.css";
import { DocsShell } from "@/components/DocsShell";
import { SITE_URL, SITE_NAME } from "@/lib/site";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "horus-os documentation",
    template: "%s",
  },
  description:
    "Official documentation for horus-os, the open-source, self-hosted autonomous AI command center. Install it, run a team of AI agents on your own machine, and extend it.",
  applicationName: SITE_NAME,
  keywords: [
    "horus-os",
    "horus-os docs",
    "horus docs",
    "horus-os documentation",
    "self-hosted AI agents",
    "autonomous AI command center",
    "local-first AI",
    "AI agent framework",
  ],
  alternates: { canonical: "/" },
  icons: { icon: "/favicon.svg" },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
  openGraph: {
    title: "horus-os documentation",
    description:
      "Run a team of AI agents on your own machine. Local-first, bring your own keys, inspect everything.",
    url: SITE_URL,
    siteName: SITE_NAME,
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "horus-os documentation",
    description:
      "Run a team of AI agents on your own machine. Local-first, bring your own keys, inspect everything.",
  },
};

export const viewport: Viewport = {
  themeColor: "#0a0b0f",
};

const JSON_LD = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: SITE_NAME,
  alternateName: "horus-os docs",
  url: SITE_URL,
  description:
    "Official documentation for horus-os, the open-source, self-hosted autonomous AI command center.",
  publisher: {
    "@type": "Organization",
    name: "horus-os",
    url: "https://github.com/Ridou/horus-os",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
        />
        <DocsShell>{children}</DocsShell>
      </body>
    </html>
  );
}
