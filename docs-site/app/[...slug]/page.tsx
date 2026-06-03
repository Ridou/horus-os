import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ExternalLink } from "lucide-react";
import { getDoc, getDocSlugs } from "@/lib/content";
import { findNavPosition } from "@/lib/nav";
import { DocMarkdown } from "@/components/DocMarkdown";
import { TableOfContents } from "@/components/TableOfContents";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { Pagination } from "@/components/Pagination";

export const dynamicParams = false;

interface Params {
  slug: string[];
}

export function generateStaticParams(): Params[] {
  return getDocSlugs().map((slug) => ({ slug: slug.split("/") }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { slug } = await params;
  const path = slug.join("/");
  const doc = getDoc(path);
  if (!doc) return {};
  return {
    title: `${doc.title} · horus-os docs`,
    description: doc.description || undefined,
    alternates: { canonical: `/${path}/` },
    openGraph: {
      title: `${doc.title} · horus-os docs`,
      description: doc.description || undefined,
      url: `/${path}/`,
      type: "article",
    },
  };
}

const EDIT_BASE =
  "https://github.com/Ridou/horus-os/blob/main/docs-site/content/docs";

export default async function DocPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { slug } = await params;
  const path = slug.join("/");
  const doc = getDoc(path);
  if (!doc) notFound();

  const { prev, next, section } = findNavPosition(path);

  return (
    <div className="flex">
      <article className="mx-auto w-full max-w-3xl px-5 py-10 sm:px-10 animate-fade-in">
        <Breadcrumbs section={section?.label ?? null} title={doc.title} />
        <h1 className="mb-3 text-[2rem] font-bold leading-tight tracking-tight text-text-primary">
          {doc.title}
        </h1>
        {doc.description && (
          <p
            className="mb-10 text-lg leading-relaxed text-text-secondary"
            style={{ fontFamily: "var(--font-sans)" }}
          >
            {doc.description}
          </p>
        )}

        <DocMarkdown content={doc.content} />

        <Pagination prev={prev} next={next} />

        <div className="mt-8 flex justify-end">
          <a
            href={`${EDIT_BASE}/${path}.md`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 font-mono text-xs text-text-muted transition-colors hover:text-accent-cyan"
          >
            Edit this page on GitHub
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </article>

      <div className="hidden w-60 shrink-0 xl:block">
        <TableOfContents toc={doc.toc} />
      </div>
    </div>
  );
}
