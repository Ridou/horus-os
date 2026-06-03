import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import GithubSlugger from "github-slugger";

/**
 * Build-time content loader. Reads markdown from content/docs, parses
 * frontmatter, and extracts a table of contents whose anchor ids match the ones
 * rehype-slug produces at render time (both use github-slugger over the heading
 * text in document order). Server-only: do not import from client components.
 */

export interface TocItem {
  depth: 2 | 3;
  text: string;
  id: string;
}

export interface Doc {
  slug: string;
  title: string;
  description: string;
  content: string;
  toc: TocItem[];
  /** Raw frontmatter for any extra fields (e.g. badge). */
  data: Record<string, unknown>;
}

const DOCS_DIR = path.join(process.cwd(), "content", "docs");

function walk(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walk(full));
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      out.push(full);
    }
  }
  return out;
}

/** Every doc slug present on disk, e.g. "guides/cli". */
export function getDocSlugs(): string[] {
  return walk(DOCS_DIR).map((full) =>
    path
      .relative(DOCS_DIR, full)
      .replace(/\.md$/, "")
      .split(path.sep)
      .join("/"),
  );
}

/** Strip inline markdown from heading text so the slug matches rehype-slug. */
function plainHeading(text: string): string {
  return text
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_~]/g, "")
    .trim();
}

function extractToc(markdown: string): TocItem[] {
  const slugger = new GithubSlugger();
  const lines = markdown.split("\n");
  const toc: TocItem[] = [];
  let inFence = false;

  for (const line of lines) {
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;

    const match = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (!match) continue;

    const depth = match[1].length;
    const text = plainHeading(match[2]);
    // Feed every heading to the slugger so duplicate numbering stays in sync
    // with rehype-slug, but only surface h2/h3 in the on-this-page rail.
    const id = slugger.slug(text);
    if (depth === 2 || depth === 3) {
      toc.push({ depth, text, id });
    }
  }
  return toc;
}

export function getDoc(slug: string): Doc | null {
  const full = path.join(DOCS_DIR, `${slug}.md`);
  if (!fs.existsSync(full)) return null;

  const raw = fs.readFileSync(full, "utf8");
  const { data, content } = matter(raw);

  const title =
    (typeof data.title === "string" && data.title) ||
    slug.split("/").pop() ||
    slug;
  const description =
    typeof data.description === "string" ? data.description : "";

  return {
    slug,
    title,
    description,
    content,
    toc: extractToc(content),
    data,
  };
}
