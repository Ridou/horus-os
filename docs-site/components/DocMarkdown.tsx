"use client";

import { isValidElement, type ReactNode } from "react";
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";
import { CodeBlock } from "./CodeBlock";
import { Callout, type CalloutType } from "./Callout";

/**
 * Tiny remark plugin: turn GitHub-style alert blockquotes
 *   > [!NOTE] ...
 * into a div carrying `callout callout-<type>` classes, with the marker
 * stripped, so DocMarkdown can render them as <Callout>.
 */
function remarkCallouts() {
  const ALERT = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/i;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const visit = (node: any) => {
    if (!node || !Array.isArray(node.children)) return;
    if (node.type === "blockquote") {
      const para = node.children[0];
      const firstText = para?.children?.[0];
      if (para?.type === "paragraph" && firstText?.type === "text") {
        const m = ALERT.exec(firstText.value);
        if (m) {
          const type = m[1].toLowerCase();
          firstText.value = firstText.value.slice(m[0].length).replace(/^\n/, "");
          if (firstText.value === "") para.children.shift();
          if (para.children.length === 0) node.children.shift();
          node.data = node.data || {};
          node.data.hName = "div";
          node.data.hProperties = {
            className: ["callout", `callout-${type}`],
          };
        }
      }
    }
    for (const child of node.children) visit(child);
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (tree: any) => visit(tree);
}

function extractText(node: ReactNode): string {
  if (node == null || node === false) return "";
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (isValidElement(node)) {
    const props = node.props as { children?: ReactNode };
    return extractText(props.children);
  }
  return "";
}

function HeadingAnchor({ id }: { id?: string }) {
  if (!id) return null;
  return (
    <a
      href={`#${id}`}
      className="heading-anchor"
      aria-label="Link to this section"
    >
      #
    </a>
  );
}

const components: Components = {
  a({ href, children }) {
    if (!href) return <span>{children}</span>;
    if (href.startsWith("#")) {
      return <a href={href}>{children}</a>;
    }
    if (href.startsWith("/")) {
      return <Link href={href}>{children}</Link>;
    }
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  },
  pre({ children }) {
    const child = Array.isArray(children) ? children[0] : children;
    if (isValidElement(child)) {
      const props = child.props as { className?: string; children?: ReactNode };
      const match = /language-(\w+)/.exec(props.className || "");
      const code = extractText(props.children).replace(/\n$/, "");
      return <CodeBlock code={code} language={match?.[1]} />;
    }
    return <pre>{children}</pre>;
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  div(props: any) {
    const className: string = props.className || "";
    const classes = className.split(/\s+/);
    if (classes.includes("callout")) {
      const typeClass = classes.find((c) => c.startsWith("callout-"));
      const type = (typeClass?.slice("callout-".length) || "note") as CalloutType;
      return <Callout type={type}>{props.children}</Callout>;
    }
    return <div className={className}>{props.children}</div>;
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  h2({ children, id }: any) {
    return (
      <h2 id={id}>
        {children}
        <HeadingAnchor id={id} />
      </h2>
    );
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  h3({ children, id }: any) {
    return (
      <h3 id={id}>
        {children}
        <HeadingAnchor id={id} />
      </h3>
    );
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  h4({ children, id }: any) {
    return (
      <h4 id={id}>
        {children}
        <HeadingAnchor id={id} />
      </h4>
    );
  },
};

/** Render documentation markdown with the horus-os doc styling. */
export function DocMarkdown({ content }: { content: string }) {
  return (
    <div className="prose-docs">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkCallouts]}
        rehypePlugins={[rehypeSlug]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default DocMarkdown;
