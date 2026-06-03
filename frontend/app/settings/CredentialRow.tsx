"use client";

import { useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { StatusDot } from "@/components";
import { api, isDemoMode } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { CredentialReplaceForm } from "./CredentialReplaceForm";
import type { IntegrationStatus, IntegrationStatusState } from "@/lib/types";

interface CredentialRowProps {
  integration: IntegrationStatus;
  onRestartRequired: () => void;
}

const STATUS_LABEL: Record<IntegrationStatusState, string> = {
  verified: "Verified",
  "configured-unverified": "Configured, not verified",
  missing: "Not configured",
  error: "Error",
};

export function CredentialRow({
  integration,
  onRestartRequired,
}: CredentialRowProps) {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [localStatus, setLocalStatus] = useState<IntegrationStatusState>(
    integration.status,
  );
  const [saveError, setSaveError] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const replaceButtonRef = useRef<HTMLButtonElement>(null);

  const saveMutation = useMutation({
    mutationFn: (value: string) => api.saveCredential(integration.id, value),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.integrations(),
      });
      setLocalStatus("configured-unverified");
      onRestartRequired();
      setFormOpen(false);
      setSaveError(null);
      setVerifyError(null);
      // Return focus to Replace button
      setTimeout(() => replaceButtonRef.current?.focus(), 0);
    },
    onError: () => {
      setSaveError(
        "Could not save credential. Check that the runtime is running locally.",
      );
    },
  });

  const verifyMutation = useMutation({
    mutationFn: () => api.verifyIntegration(integration.id),
    onSuccess: (data) => {
      if (data.ok) {
        setLocalStatus("verified");
        setVerifyError(null);
      } else {
        setLocalStatus("error");
        setVerifyError("Verification failed. Check the value and try again.");
      }
    },
    onError: () => {
      setLocalStatus("error");
      setVerifyError("Verification failed. Check the value and try again.");
    },
  });

  const isSet = localStatus !== "missing";

  return (
    <div className="py-3">
      {/* Row 1: name/env-var on left, status+actions on right */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-bold text-text-primary">
            {integration.name}
          </p>
          <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-text-muted">
            {integration.env_var}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <StatusDot state={localStatus} size="sm" />
          <span className="text-xs text-text-secondary">
            {STATUS_LABEL[localStatus]}
          </span>
          {isSet && !isDemoMode && (
            <button
              type="button"
              onClick={() => verifyMutation.mutate()}
              disabled={verifyMutation.isPending}
              aria-label={`Verify ${integration.name}`}
              className="text-xs font-bold text-text-secondary hover:text-accent-cyan disabled:opacity-50"
            >
              {verifyMutation.isPending ? "Verifying..." : "Verify now"}
            </button>
          )}
        </div>
      </div>

      {/* Row 2: masked value + replace trigger */}
      <div className="mt-1.5 flex items-center gap-3">
        {isSet ? (
          <span className="font-mono text-xs text-text-muted">
            {"••••••••"}
          </span>
        ) : (
          <span className="text-xs text-text-muted">Not set</span>
        )}
        {!isDemoMode && (
          <button
            ref={replaceButtonRef}
            type="button"
            aria-expanded={formOpen}
            aria-label={`Replace ${integration.env_var}`}
            onClick={() => {
              setFormOpen((prev) => !prev);
              setSaveError(null);
              setVerifyError(null);
            }}
            className="text-xs text-text-secondary hover:text-text-primary"
          >
            Replace
          </button>
        )}
      </div>

      {/* Demo mode notice */}
      {isDemoMode && (
        <p className="mt-1 text-xs italic text-text-muted py-1">
          Credential management is disabled in demo mode.
        </p>
      )}

      {/* Replace form (non-demo only) */}
      {!isDemoMode && formOpen && (
        <CredentialReplaceForm
          envVar={integration.env_var}
          pending={saveMutation.isPending}
          onSave={(value) => saveMutation.mutate(value)}
          onCancel={() => {
            setFormOpen(false);
            setSaveError(null);
          }}
        />
      )}

      {/* Save error */}
      {saveError && (
        <p role="alert" className="mt-1 text-xs text-danger">
          {saveError}
        </p>
      )}

      {/* Verify error */}
      {verifyError && (
        <p role="alert" className="mt-1 text-xs text-danger">
          {verifyError}
        </p>
      )}
    </div>
  );
}
