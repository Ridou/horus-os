"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import {
  Lock,
  Cpu,
  FolderOpen,
  Database,
  Users,
  Brain,
  Network,
  KeyRound,
  AlertTriangle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useSettings, useIntegrations } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/PageSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { isDemoMode } from "@/lib/api";
import { CredentialRow } from "./CredentialRow";

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[10px] uppercase tracking-wider text-text-muted">
        {label}
      </dt>
      <dd
        className={
          mono
            ? "break-all font-mono text-xs text-text-primary"
            : "text-sm font-medium text-text-primary"
        }
      >
        {value}
      </dd>
    </div>
  );
}

function Card({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <section className="border border-border-subtle bg-bg-secondary p-4">
      <h2 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-text-secondary">
        <Icon className="h-3.5 w-3.5 text-text-muted" />
        {title}
      </h2>
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">{children}</dl>
    </section>
  );
}

function CountTile({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
}) {
  return (
    <div className="flex items-center gap-3 border border-border-subtle bg-bg-secondary p-4 border-glow">
      <span className="rounded-md bg-bg-elevated p-2">
        <Icon className="h-4 w-4 text-accent-cyan" />
      </span>
      <div>
        <p className="text-xl font-bold leading-none text-text-primary tabular-nums">
          {value.toLocaleString()}
        </p>
        <p className="mt-1 text-[10px] uppercase tracking-wider text-text-muted">
          {label}
        </p>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { data, isLoading } = useSettings();
  const {
    data: integrationsData,
    isLoading: integrationsLoading,
    isError: integrationsError,
  } = useIntegrations();
  const [restartRequired, setRestartRequired] = useState(false);

  return (
    <div>
      <PageHeader
        title="Settings"
        description="The resolved configuration this instance is running with. Credentials can be updated below."
      />

      {/* Read-only notice */}
      <div className="mb-6 flex items-start gap-3 border border-border-subtle bg-bg-secondary p-3 gradient-cyber">
        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan" />
        <p className="text-xs text-text-secondary">
          This view is read-only. Configuration lives in your TOML config file
          and is edited with{" "}
          <code className="rounded bg-bg-primary px-1.5 py-0.5 font-mono text-[11px] text-text-primary">
            horus-os init
          </code>
          . Restart the runtime to pick up changes.
        </p>
      </div>

      {isLoading ? (
        <PageSkeleton variant="dashboard" />
      ) : !data ? (
        <EmptyState icon={Lock} message="Could not load settings." />
      ) : (
        <div className="space-y-4">
          {/* Counts */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <CountTile label="Agents" value={data.counts.agents} icon={Users} />
            <CountTile label="Notes" value={data.counts.notes} icon={Brain} />
            <CountTile
              label="Traces"
              value={data.counts.traces}
              icon={Network}
            />
          </div>

          <Card title="Providers and models" icon={Cpu}>
            <Field label="Default provider" value={data.default_provider} />
            <Field label="Anthropic model" value={data.anthropic_model} mono />
            <Field label="Gemini model" value={data.gemini_model} mono />
          </Card>

          <Card title="Storage locations" icon={FolderOpen}>
            <Field label="Data directory" value={data.data_dir} mono />
            <Field label="Notes directory" value={data.notes_dir} mono />
            <Field label="Database path" value={data.db_path} mono />
          </Card>

          <Card title="Versions" icon={Database}>
            <Field label="App version" value={data.version} mono />
            <Field
              label="Schema version"
              value={String(data.schema_version)}
              mono
            />
          </Card>

          {/* Restart banner - shown after any credential save this session, anchored above Credentials */}
          {restartRequired && !isDemoMode && (
            <div
              role="status"
              className="border border-warning/30 bg-bg-secondary p-3 flex items-start gap-3"
            >
              <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" />
              <p className="text-xs text-text-secondary">
                A credential was updated. Restart the horus-os runtime to apply
                it, then verify the integration.
              </p>
            </div>
          )}

          {/* Credentials section */}
          {integrationsLoading ? (
            <PageSkeleton variant="list" />
          ) : integrationsError ? (
            <EmptyState icon={Lock} message="Could not load credentials." />
          ) : integrationsData ? (
            <section className="border border-border-subtle bg-bg-secondary p-4">
              <h2 className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-text-secondary">
                <KeyRound className="h-3.5 w-3.5 text-text-muted" />
                Credentials
              </h2>
              <div className="divide-y divide-border-subtle">
                {integrationsData.integrations.map((integration) => (
                  <CredentialRow
                    key={integration.id}
                    integration={integration}
                    onRestartRequired={() => setRestartRequired(true)}
                  />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}
