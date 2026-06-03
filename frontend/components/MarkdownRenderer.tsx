"use client";

import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

interface MarkdownRendererProps {
  content: string;
  /** Called when a [[wikilink]] is clicked, with the decoded note name. */
  onNavigate?: (noteName: string) => void;
  /** Optional term to highlight in headings and paragraphs. */
  searchQuery?: string;
}

function stripFrontmatter(text: string): string {
  if (text.startsWith("---")) {
    const end = text.indexOf("---", 3);
    if (end !== -1) return text.slice(end + 3).trim();
  }
  return text;
}

function preprocess(raw: string): string {
  let text = stripFrontmatter(raw);
  // [[Note Name]] -> link with a custom scheme handled in the renderer.
  text = text.replace(
    /\[\[([^\]]+)\]\]/g,
    (_, name) => `[${name}](#note:${encodeURIComponent(name)})`,
  );
  // Inline #tag -> a code span marker, skipping content inside code fences.
  text = text.replace(/(?<=\s|^(?!#))#([a-zA-Z][\w-]*)/gm, (match, tag, offset) => {
    const before = text.slice(0, offset);
    const fenceCount = (before.match(/```/g) || []).length;
    if (fenceCount % 2 !== 0) return match;
    return ` \`#TAG:${tag}\``;
  });
  return text;
}

function Highlight({ text, query }: { text: string; query?: string }) {
  if (!query || !query.trim()) return <>{text}</>;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase() ? (
          <mark
            key={i}
            style={{
              background: "rgba(0, 212, 255, 0.2)",
              color: "inherit",
              borderRadius: "2px",
              padding: "0 2px",
            }}
          >
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}

/**
 * Markdown renderer with GitHub-flavored markdown, [[wikilinks]], #tags, and
 * optional search highlighting. Styled via the `.markdown-content` scope in
 * globals.css.
 */
export function MarkdownRenderer({
  content,
  onNavigate,
  searchQuery,
}: MarkdownRendererProps) {
  const processed = useMemo(() => preprocess(content || ""), [content]);

  const components: Components = useMemo(
    () => ({
      a: ({ href, children }) => {
        if (href?.startsWith("#note:")) {
          const noteName = decodeURIComponent(href.slice("#note:".length));
          return (
            <button
              type="button"
              onClick={() => onNavigate?.(noteName)}
              className="cursor-pointer underline"
              style={{ color: "var(--accent-cyan)" }}
            >
              {children}
            </button>
          );
        }
        return (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--accent-cyan)" }}
          >
            {children}
          </a>
        );
      },
      code: ({ children, className }) => {
        const isBlock = !!className;
        const text = String(children).replace(/\n$/, "");
        if (!isBlock && text.startsWith("#TAG:")) {
          const tag = text.slice("#TAG:".length);
          return (
            <span
              className="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{
                background: "rgba(0, 212, 255, 0.15)",
                color: "var(--accent-cyan)",
              }}
            >
              #{tag}
            </span>
          );
        }
        if (isBlock) {
          return (
            <code
              className={`font-mono text-xs ${className ?? ""}`}
              style={{ color: "var(--text-secondary)" }}
            >
              {searchQuery ? (
                <Highlight text={text} query={searchQuery} />
              ) : (
                text
              )}
            </code>
          );
        }
        return (
          <code
            className="rounded px-1 py-0.5 font-mono text-xs"
            style={{
              background: "var(--bg-primary)",
              color: "var(--text-secondary)",
            }}
          >
            {text}
          </code>
        );
      },
      pre: ({ children }) => (
        <pre
          className="my-2 overflow-x-auto rounded p-3 text-xs"
          style={{ background: "var(--bg-primary)" }}
        >
          {children}
        </pre>
      ),
      h1: ({ children }) => (
        <h1
          className="mb-3 mt-4 text-lg font-bold"
          style={{ color: "var(--accent-cyan)" }}
        >
          {searchQuery ? (
            <Highlight text={String(children)} query={searchQuery} />
          ) : (
            children
          )}
        </h1>
      ),
      h2: ({ children }) => (
        <h2
          className="mb-2 mt-3 text-base font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          {searchQuery ? (
            <Highlight text={String(children)} query={searchQuery} />
          ) : (
            children
          )}
        </h2>
      ),
      h3: ({ children }) => (
        <h3
          className="mb-2 mt-3 text-sm font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          {searchQuery ? (
            <Highlight text={String(children)} query={searchQuery} />
          ) : (
            children
          )}
        </h3>
      ),
      p: ({ children }) => (
        <p
          className="mb-2 text-sm leading-relaxed"
          style={{ color: "var(--text-secondary)" }}
        >
          {children}
        </p>
      ),
      ul: ({ children }) => (
        <ul
          className="mb-2 list-inside list-disc text-sm"
          style={{ color: "var(--text-secondary)" }}
        >
          {children}
        </ul>
      ),
      ol: ({ children }) => (
        <ol
          className="mb-2 list-inside list-decimal text-sm"
          style={{ color: "var(--text-secondary)" }}
        >
          {children}
        </ol>
      ),
      li: ({ children }) => <li className="mb-0.5">{children}</li>,
    }),
    [onNavigate, searchQuery],
  );

  if (!content) {
    return (
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        No content
      </p>
    );
  }

  return (
    <div className="markdown-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {processed}
      </ReactMarkdown>
    </div>
  );
}

export default MarkdownRenderer;
