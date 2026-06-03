"use client";

/** Replaces the Stepper CTA footer in demo mode. Instructional-only. */
export function DemoModeNotice() {
  return (
    <p className="mt-2 text-center text-xs text-text-muted py-2">
      Walkthrough is view-only in demo mode. Install horus-os to configure integrations.
    </p>
  );
}
