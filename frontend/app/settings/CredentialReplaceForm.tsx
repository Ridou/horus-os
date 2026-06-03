"use client";

import { useState } from "react";

interface CredentialReplaceFormProps {
  envVar: string;
  pending: boolean;
  onSave: (value: string) => void;
  onCancel: () => void;
}

export function CredentialReplaceForm({
  envVar,
  pending,
  onSave,
  onCancel,
}: CredentialReplaceFormProps) {
  const [inputValue, setInputValue] = useState("");

  function handleSave() {
    if (!inputValue || pending) return;
    onSave(inputValue);
  }

  const saveDisabled = !inputValue || pending;

  return (
    <div className="mt-2 flex flex-col gap-2">
      <input
        type="password"
        autoComplete="new-password"
        placeholder="Paste new value..."
        aria-label={`New value for ${envVar}`}
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        disabled={pending}
        className="w-full bg-bg-secondary text-sm text-text-primary placeholder:text-text-muted
                   border border-border-subtle px-3 py-2 focus:outline-none focus:ring-1
                   focus:ring-accent-cyan"
      />
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saveDisabled}
          aria-disabled={saveDisabled}
          className="bg-accent-cyan text-bg-primary text-xs font-bold px-3 py-1 disabled:opacity-40"
        >
          {pending ? "Saving..." : "Save credential"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs text-text-secondary hover:text-text-primary"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
