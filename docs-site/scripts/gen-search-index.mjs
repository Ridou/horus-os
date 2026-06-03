// Generates public/search-index.json from content/docs at build time.
// Runs in `prebuild` and `predev`. Self-contained: no TypeScript imports.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import matter from "gray-matter";

const root = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.join(root, "..");
const DOCS_DIR = path.join(projectRoot, "content", "docs");
const OUT = path.join(projectRoot, "public", "search-index.json");

function walk(dir) {
  if (!fs.existsSync(dir)) return [];
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (entry.isFile() && entry.name.endsWith(".md")) out.push(full);
  }
  return out;
}

// Cheap markdown -> plain text for the search corpus.
function toPlain(md) {
  return md
    .replace(/```[\s\S]*?```/g, " ")        // fenced code
    .replace(/`[^`]*`/g, " ")               // inline code
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")  // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1") // links -> text
    .replace(/^#{1,6}\s+/gm, " ")           // heading marks
    .replace(/[*_>#~|-]+/g, " ")            // residual marks
    .replace(/\s+/g, " ")
    .trim();
}

function headings(md) {
  const out = [];
  let inFence = false;
  for (const line of md.split("\n")) {
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    const m = /^(#{2,3})\s+(.+?)\s*#*\s*$/.exec(line);
    if (m) out.push(m[2].replace(/`/g, "").trim());
  }
  return out;
}

const records = walk(DOCS_DIR).map((full) => {
  const slug = path
    .relative(DOCS_DIR, full)
    .replace(/\.md$/, "")
    .split(path.sep)
    .join("/");
  const { data, content } = matter(fs.readFileSync(full, "utf8"));
  return {
    slug,
    title: typeof data.title === "string" ? data.title : slug,
    description: typeof data.description === "string" ? data.description : "",
    headings: headings(content),
    body: toPlain(content).slice(0, 8000),
  };
});

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(records));
console.log(`[gen-search-index] wrote ${records.length} records to ${path.relative(projectRoot, OUT)}`);
