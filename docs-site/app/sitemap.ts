import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";
import { getDocSlugs } from "@/lib/content";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const docs = getDocSlugs().map((slug) => ({
    url: `${SITE_URL}/${slug}/`,
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));
  return [
    { url: `${SITE_URL}/`, changeFrequency: "weekly", priority: 1 },
    ...docs,
  ];
}
