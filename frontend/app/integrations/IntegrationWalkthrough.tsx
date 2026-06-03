"use client";

import { Modal, Stepper, CommandBlock } from "@/components";
import type { StepperStep } from "@/components";
import { isDemoMode } from "@/lib/api";
import { DemoModeNotice } from "./DemoModeNotice";
import type { IntegrationStatus } from "@/lib/types";

interface IntegrationWalkthroughProps {
  integration: IntegrationStatus;
  open: boolean;
  onClose: () => void;
  currentStep: number;
  onStepChange: (step: number) => void;
  demoMode?: boolean;
}

export function IntegrationWalkthrough({
  integration,
  open,
  onClose,
  currentStep,
  onStepChange,
  demoMode = false,
}: IntegrationWalkthroughProps) {
  const effectiveDemoMode = isDemoMode || demoMode;

  const steps: StepperStep[] = [
    {
      title: `What ${integration.name} unlocks`,
      children: (
        <p className="text-sm text-text-secondary">{integration.description}</p>
      ),
    },
    {
      title: "Where to get your credentials",
      children: integration.credential_portal_url ? (
        <p className="text-sm text-text-secondary">
          Visit the{" "}
          <a
            href={integration.credential_portal_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-cyan hover:underline"
          >
            {integration.name} credentials portal
          </a>{" "}
          to create your API key or token.
        </p>
      ) : (
        <p className="text-sm text-text-secondary">
          Configure your credentials as environment variables below.
        </p>
      ),
    },
    {
      title: "Add to your environment",
      children: (
        <div className="space-y-2">
          {integration.required_vars.map((varName) => (
            <CommandBlock key={varName} command={`export ${varName}=your-value-here`} />
          ))}
        </div>
      ),
    },
  ];

  const currentStepData = steps[currentStep] ?? steps[0];

  return (
    <Modal
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) onClose();
      }}
      title={integration.name}
      description={integration.description}
      size="md"
    >
      {effectiveDemoMode ? (
        <div>
          {/* Read-only step view in demo mode - informational Prev/Next only, no write actions */}
          <div className="border border-border-subtle bg-bg-secondary p-4">
            <h2 className="mb-4 text-base font-bold text-text-primary">
              {currentStepData.title}
            </h2>
            <div className="space-y-3">{currentStepData.children}</div>
          </div>
          <div className="mt-4 flex items-center justify-between">
            {currentStep === 0 ? (
              <span aria-hidden="true" />
            ) : (
              <button
                type="button"
                onClick={() => onStepChange(currentStep - 1)}
                className="text-sm text-text-secondary hover:text-text-primary"
              >
                Prev
              </button>
            )}
            <span className="text-xs text-text-muted">
              Step {currentStep + 1} of {steps.length}
            </span>
            {currentStep < steps.length - 1 ? (
              <button
                type="button"
                onClick={() => onStepChange(currentStep + 1)}
                className="text-sm text-text-secondary hover:text-text-primary"
              >
                Next
              </button>
            ) : (
              <span aria-hidden="true" />
            )}
          </div>
          <DemoModeNotice />
        </div>
      ) : (
        <Stepper
          steps={steps}
          currentStep={currentStep}
          onStepChange={onStepChange}
          onComplete={onClose}
          completeLabel="Done"
        />
      )}
    </Modal>
  );
}
