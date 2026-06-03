"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  MessageSquare,
  Loader2,
  Network,
  Send,
  Square,
  Wrench,
} from "lucide-react";
import { api, isDemoMode } from "@/lib/api";
import { useAgents } from "@/lib/hooks";
import { cn } from "@/lib/cn";
import type { ChatStreamEvent } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";

/** One tool the model invoked, surfaced inline under the assistant turn. */
interface ToolCall {
  name: string;
  input: Record<string, unknown>;
}

/** A single turn in the running conversation. */
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  traceId: string | null;
  error: string | null;
}

function ChatView() {
  const searchParams = useSearchParams();
  const { data: agentsData } = useAgents();
  const agents = agentsData?.agents ?? [];

  const [selectedAgent, setSelectedAgent] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const autoSentRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  /** Mutate the trailing assistant message in place. */
  function patchAssistant(fn: (m: ChatMessage) => ChatMessage) {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last && last.role === "assistant") {
        next[next.length - 1] = fn(last);
      }
      return next;
    });
  }

  async function send(prompt: string) {
    const q = prompt.trim();
    if (!q || streaming) return;
    setInput("");
    setStreaming(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: q, toolCalls: [], traceId: null, error: null },
      {
        role: "assistant",
        content: "",
        toolCalls: [],
        traceId: null,
        error: null,
      },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await api.chatStream(
        { prompt: q, agent: selectedAgent || undefined },
        (event: ChatStreamEvent) => {
          if (event.type === "token" && event.text) {
            patchAssistant((m) => ({ ...m, content: m.content + event.text }));
          } else if (event.type === "tool_call" && event.name) {
            patchAssistant((m) => ({
              ...m,
              toolCalls: [
                ...m.toolCalls,
                { name: event.name as string, input: event.input ?? {} },
              ],
            }));
          } else if (event.type === "done") {
            patchAssistant((m) => ({ ...m, traceId: event.trace_id ?? null }));
          } else if (event.type === "error") {
            patchAssistant((m) => ({
              ...m,
              error: event.message ?? "The run failed.",
            }));
          }
        },
        controller.signal,
      );
    } catch {
      if (!controller.signal.aborted) {
        patchAssistant((m) => ({
          ...m,
          error:
            "Could not reach the backend. A local horus-os server is required to chat.",
        }));
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  }

  // Deep link: /chat?q=... prefills and auto-sends one prompt (used by the
  // home quick-prompt and command palette). Skipped in demo mode.
  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !autoSentRef.current && !isDemoMode) {
      autoSentRef.current = true;
      void send(q);
    }
    // send is stable enough for this one-shot effect; deps intentionally minimal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Keep the latest turn in view as tokens stream in. Optional-chain the call
  // so jsdom (no scrollTo) and older browsers do not throw.
  useEffect(() => {
    scrollRef.current?.scrollTo?.({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Chat"
        description="Talk to your agents. Pick a team member or use the default, then send a prompt and watch the reply stream."
        actions={
          agents.length > 0 ? (
            <label className="flex items-center gap-2 text-xs text-text-secondary">
              <span className="font-bold">Agent</span>
              <select
                aria-label="Agent"
                value={selectedAgent}
                onChange={(e) => setSelectedAgent(e.target.value)}
                disabled={streaming}
                className="border border-border-subtle bg-bg-secondary px-2 py-1 text-xs text-text-primary focus:border-accent-cyan focus:outline-none disabled:opacity-50"
              >
                <option value="">Default</option>
                {agents.map((a) => (
                  <option key={a.name} value={a.name}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
          ) : undefined
        }
      />

      {isDemoMode && (
        <p className="mb-4 border border-accent-cyan/30 bg-accent-cyan/5 px-4 py-3 text-xs text-text-secondary">
          Chat is disabled in the hosted demo. Run horus-os locally with{" "}
          <code className="text-accent-cyan">horus-os serve</code> to talk to
          your agents.
        </p>
      )}

      {/* Conversation transcript */}
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto pb-4"
      >
        {messages.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            heading="Start a conversation"
            message="Ask a question, request a task, or hand work to a specific agent. Every reply is traced so you can inspect exactly what ran."
          />
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                "flex",
                m.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] border px-4 py-3 text-sm",
                  m.role === "user"
                    ? "border-accent-cyan/30 bg-accent-cyan/5 text-text-primary"
                    : "border-border-subtle bg-bg-secondary text-text-primary",
                )}
              >
                {m.role === "user" ? (
                  <p className="whitespace-pre-wrap">{m.content}</p>
                ) : (
                  <>
                    {m.toolCalls.map((t, ti) => (
                      <div
                        key={ti}
                        className="mb-2 inline-flex items-center gap-1.5 border border-border-subtle bg-bg-elevated px-2 py-1 text-[11px] font-bold text-text-secondary"
                      >
                        <Wrench className="h-3 w-3 text-accent-cyan" />
                        {t.name}
                      </div>
                    ))}
                    {m.content ? (
                      <MarkdownRenderer content={m.content} />
                    ) : (
                      !m.error && (
                        <span className="inline-flex items-center gap-2 text-text-muted">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Thinking
                        </span>
                      )
                    )}
                    {m.error && (
                      <p className="mt-1 text-xs text-danger">{m.error}</p>
                    )}
                    {m.traceId && (
                      <div className="mt-3 border-t border-border-subtle pt-2 text-xs">
                        <Link
                          href={`/traces?trace=${encodeURIComponent(m.traceId)}`}
                          className="inline-flex items-center gap-1.5 font-bold text-accent-cyan hover:underline"
                        >
                          <Network className="h-3.5 w-3.5" />
                          View trace
                        </Link>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-border-subtle pt-3">
        <div className="flex items-end gap-2">
          <textarea
            aria-label="Message"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            placeholder="Ask your team anything. Enter to send, Shift+Enter for a new line."
            disabled={isDemoMode}
            className="min-h-0 flex-1 resize-y border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-cyan focus:outline-none disabled:opacity-50"
          />
          {streaming ? (
            <button
              type="button"
              onClick={stop}
              className="inline-flex items-center gap-2 bg-bg-elevated px-4 py-2 text-sm font-bold text-text-primary"
            >
              <Square className="h-4 w-4" />
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void send(input)}
              disabled={isDemoMode || !input.trim()}
              className="inline-flex items-center gap-2 bg-accent-cyan px-4 py-2 text-sm font-bold text-bg-primary transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Static export bails out of client-side rendering unless a component that
 * reads useSearchParams is wrapped in a Suspense boundary, so the route export
 * provides one around the view.
 */
export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div>
          <PageHeader title="Chat" description="Loading your conversation." />
        </div>
      }
    >
      <ChatView />
    </Suspense>
  );
}
