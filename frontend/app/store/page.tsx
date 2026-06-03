"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Store, Plus, Check, Loader2, Wrench, Plug } from "lucide-react";
import { api, isDemoMode } from "@/lib/api";
import { useStoreBundles } from "@/lib/hooks";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/cn";
import type { CreateAgentRequest } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/PageSkeleton";

type Tab = "browse" | "create";

export default function StorePage() {
  const [tab, setTab] = useState<Tab>("browse");

  return (
    <div>
      <PageHeader
        title="Agent store"
        description="Install a ready-made agent or build your own. Installed agents show up on your team and in chat."
        actions={
          <div className="flex items-center gap-1 border border-border-subtle p-0.5">
            <TabButton active={tab === "browse"} onClick={() => setTab("browse")}>
              Browse
            </TabButton>
            <TabButton active={tab === "create"} onClick={() => setTab("create")}>
              Create
            </TabButton>
          </div>
        }
      />

      {tab === "browse" ? <BrowseBundles /> : <CreateAgent />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-3 py-1 text-xs font-bold transition-colors",
        active
          ? "bg-accent-cyan/10 text-accent-cyan"
          : "text-text-secondary hover:text-text-primary",
      )}
    >
      {children}
    </button>
  );
}

function BrowseBundles() {
  const { data, isLoading } = useStoreBundles();
  const queryClient = useQueryClient();
  const [installing, setInstalling] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const bundles = data?.bundles ?? [];

  async function install(slug: string) {
    setInstalling(slug);
    setError(null);
    try {
      await api.installBundle(slug);
      await queryClient.invalidateQueries({ queryKey: queryKeys.storeBundles() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.agents() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.team() });
    } catch {
      setError(
        "Could not install this agent. A local backend is required to install.",
      );
    } finally {
      setInstalling(null);
    }
  }

  if (isLoading) return <PageSkeleton variant="list" />;

  return (
    <div className="space-y-4">
      {error && (
        <p className="border border-danger/30 bg-danger/5 px-4 py-3 text-xs text-danger">
          {error}
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {bundles.map((b) => (
          <div
            key={b.slug}
            className="flex flex-col gap-3 border border-border-subtle bg-bg-secondary p-4"
          >
            <div className="flex items-start gap-3">
              <span
                className="mt-1 h-3 w-3 shrink-0 rounded-full"
                style={{ backgroundColor: b.color }}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold text-text-primary">
                    {b.name}
                  </span>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">
                    {b.role}
                  </span>
                </div>
                <p className="mt-1 text-xs text-text-secondary">{b.description}</p>
              </div>
            </div>

            {b.recommended_tools.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {b.recommended_tools.slice(0, 4).map((t) => (
                  <span
                    key={t}
                    className="inline-flex items-center gap-1 border border-border-subtle bg-bg-elevated px-1.5 py-0.5 text-[10px] text-text-muted"
                  >
                    <Wrench className="h-2.5 w-2.5" />
                    {t}
                  </span>
                ))}
              </div>
            )}

            {b.recommended_adapters.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {b.recommended_adapters.map((a) => (
                  <span
                    key={a}
                    className="inline-flex items-center gap-1 border border-border-subtle px-1.5 py-0.5 text-[10px] text-text-muted"
                  >
                    <Plug className="h-2.5 w-2.5" />
                    {a}
                  </span>
                ))}
              </div>
            )}

            <div className="mt-auto pt-1">
              {b.installed ? (
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-success">
                  <Check className="h-3.5 w-3.5" />
                  Installed
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => install(b.slug)}
                  disabled={isDemoMode || installing === b.slug}
                  className="inline-flex items-center gap-1.5 bg-accent-cyan px-3 py-1.5 text-xs font-bold text-bg-primary transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {installing === b.slug ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Plus className="h-3.5 w-3.5" />
                  )}
                  Install
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
      {isDemoMode && (
        <p className="text-xs text-text-muted">
          Installing is disabled in the hosted demo. Run horus-os locally to add
          these agents to your team.
        </p>
      )}
    </div>
  );
}

function CreateAgent() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState("#00d4ff");
  const [model, setModel] = useState("");
  const [tools, setTools] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<string | null>(null);

  async function submit() {
    if (!name.trim() || !systemPrompt.trim()) return;
    setSaving(true);
    setError(null);
    setCreated(null);
    const allowed = tools
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    const payload: CreateAgentRequest = {
      name: name.trim(),
      system_prompt: systemPrompt.trim(),
      description: description.trim() || undefined,
      color: color || undefined,
      default_model: model.trim() || undefined,
      allowed_tools: allowed.length > 0 ? allowed : undefined,
    };
    try {
      await api.createAgent(payload);
      await queryClient.invalidateQueries({ queryKey: queryKeys.agents() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.team() });
      setCreated(payload.name);
      setName("");
      setDescription("");
      setModel("");
      setTools("");
      setSystemPrompt("");
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not create the agent. A local backend is required.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-4">
      {created && (
        <p className="border border-success/30 bg-success/5 px-4 py-3 text-xs text-success">
          Created {created}. It is now on your team and available in chat.
        </p>
      )}
      {error && (
        <p className="border border-danger/30 bg-danger/5 px-4 py-3 text-xs text-danger">
          {error}
        </p>
      )}

      <Field label="Name" htmlFor="agent-name">
        <input
          id="agent-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Scout"
          className={inputClass}
        />
      </Field>

      <Field label="Role / description" htmlFor="agent-desc">
        <input
          id="agent-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Finds and summarizes competitor news"
          className={inputClass}
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Accent color" htmlFor="agent-color">
          <input
            id="agent-color"
            value={color}
            onChange={(e) => setColor(e.target.value)}
            placeholder="#00d4ff"
            className={inputClass}
          />
        </Field>
        <Field label="Default model (optional)" htmlFor="agent-model">
          <input
            id="agent-model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="inherits the configured model"
            className={inputClass}
          />
        </Field>
      </div>

      <Field label="Tools (comma separated, optional)" htmlFor="agent-tools">
        <input
          id="agent-tools"
          value={tools}
          onChange={(e) => setTools(e.target.value)}
          placeholder="web_search, create_note"
          className={inputClass}
        />
      </Field>

      <Field label="System prompt" htmlFor="agent-prompt">
        <textarea
          id="agent-prompt"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          rows={6}
          placeholder="You are Scout. You track and summarize..."
          className={cn(inputClass, "resize-y")}
        />
      </Field>

      <button
        type="button"
        onClick={submit}
        disabled={isDemoMode || saving || !name.trim() || !systemPrompt.trim()}
        className="inline-flex items-center gap-2 bg-accent-cyan px-4 py-2 text-sm font-bold text-bg-primary transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
      >
        {saving ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Store className="h-4 w-4" />
        )}
        Create agent
      </button>
      {isDemoMode && (
        <p className="text-xs text-text-muted">
          Creating agents is disabled in the hosted demo.
        </p>
      )}
    </div>
  );
}

const inputClass =
  "w-full border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-cyan focus:outline-none";

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-xs font-bold text-text-secondary">
        {label}
      </label>
      {children}
    </div>
  );
}
