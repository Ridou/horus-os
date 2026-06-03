"use client";

import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript";
import tsx from "react-syntax-highlighter/dist/esm/languages/prism/tsx";
import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript";
import jsonLang from "react-syntax-highlighter/dist/esm/languages/prism/json";
import yaml from "react-syntax-highlighter/dist/esm/languages/prism/yaml";
import toml from "react-syntax-highlighter/dist/esm/languages/prism/toml";
import ini from "react-syntax-highlighter/dist/esm/languages/prism/ini";
import markdown from "react-syntax-highlighter/dist/esm/languages/prism/markdown";
import sql from "react-syntax-highlighter/dist/esm/languages/prism/sql";
import { CopyButton } from "./CopyButton";

SyntaxHighlighter.registerLanguage("bash", bash);
SyntaxHighlighter.registerLanguage("sh", bash);
SyntaxHighlighter.registerLanguage("shell", bash);
SyntaxHighlighter.registerLanguage("python", python);
SyntaxHighlighter.registerLanguage("py", python);
SyntaxHighlighter.registerLanguage("typescript", typescript);
SyntaxHighlighter.registerLanguage("ts", typescript);
SyntaxHighlighter.registerLanguage("tsx", tsx);
SyntaxHighlighter.registerLanguage("javascript", javascript);
SyntaxHighlighter.registerLanguage("js", javascript);
SyntaxHighlighter.registerLanguage("json", jsonLang);
SyntaxHighlighter.registerLanguage("yaml", yaml);
SyntaxHighlighter.registerLanguage("yml", yaml);
SyntaxHighlighter.registerLanguage("toml", toml);
SyntaxHighlighter.registerLanguage("ini", ini);
SyntaxHighlighter.registerLanguage("markdown", markdown);
SyntaxHighlighter.registerLanguage("md", markdown);
SyntaxHighlighter.registerLanguage("sql", sql);

const LANG_LABELS: Record<string, string> = {
  bash: "bash",
  sh: "shell",
  shell: "shell",
  python: "python",
  py: "python",
  typescript: "typescript",
  ts: "typescript",
  tsx: "tsx",
  javascript: "javascript",
  js: "javascript",
  json: "json",
  yaml: "yaml",
  yml: "yaml",
  toml: "toml",
  ini: "ini",
  text: "text",
};

/** A fenced code block with a language label and a copy button. */
export function CodeBlock({
  code,
  language,
}: {
  code: string;
  language?: string;
}) {
  const lang = (language || "text").toLowerCase();
  const known = lang in LANG_LABELS || isRegistered(lang);
  const label = LANG_LABELS[lang] ?? lang;

  return (
    <div className="group relative my-5 overflow-hidden rounded-md border border-border-subtle bg-[#07080c]">
      <div className="flex items-center justify-between border-b border-border-subtle bg-bg-secondary px-3 py-1.5">
        <span className="font-mono text-[11px] uppercase tracking-wider text-text-muted">
          {label}
        </span>
        <CopyButton value={code} className="border-transparent bg-transparent px-1.5 py-0.5 hover:bg-bg-elevated" />
      </div>
      <SyntaxHighlighter
        language={known ? lang : undefined}
        style={oneDark}
        PreTag="div"
        customStyle={{
          margin: 0,
          padding: "1rem 1.1rem",
          background: "transparent",
          fontSize: "0.8125rem",
          lineHeight: 1.6,
        }}
        codeTagProps={{
          style: {
            fontFamily:
              "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
          },
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

function isRegistered(lang: string): boolean {
  try {
    return Boolean(
      (SyntaxHighlighter as unknown as {
        supportedLanguages?: string[];
      }).supportedLanguages?.includes(lang),
    );
  } catch {
    return false;
  }
}
