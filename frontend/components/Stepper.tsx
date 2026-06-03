"use client";

export interface StepperStep {
  title: string;
  description?: string;
  isValid?: boolean;
  children: React.ReactNode;
}

export interface StepperProps {
  steps: StepperStep[];
  currentStep: number;
  onStepChange: (step: number) => void;
  onComplete: () => void;
  completeLabel?: string;
  isLoading?: boolean;
}

/** Controlled multi-step wizard primitive. */
export function Stepper({
  steps,
  currentStep,
  onStepChange,
  onComplete,
  completeLabel = "Finish setup",
  isLoading = false,
}: StepperProps) {
  const total = steps.length;
  const isLastStep = currentStep === total - 1;
  const currentStepData = steps[currentStep];
  const isValid = currentStepData?.isValid !== false;
  const ctaDisabled = !isValid || isLoading;

  function handlePrimary() {
    if (ctaDisabled) return;
    if (isLastStep) {
      onComplete();
    } else {
      onStepChange(currentStep + 1);
    }
  }

  function handleBack() {
    onStepChange(currentStep - 1);
  }

  return (
    <div
      role="group"
      aria-label={`Step ${currentStep + 1} of ${total}`}
    >
      {/* Progress indicator row */}
      <div
        role="region"
        aria-live="polite"
        className="flex items-center gap-2"
      >
        {steps.map((step, index) => {
          const isActive = index === currentStep;
          const isCompleted = index < currentStep;
          const isFuture = index > currentStep;

          let bubbleClasses =
            "h-7 w-7 rounded-full flex items-center justify-center text-sm font-bold tabular-nums shrink-0 ";

          if (isActive) {
            bubbleClasses +=
              "bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30";
          } else if (isCompleted) {
            bubbleClasses +=
              "bg-success/10 text-success border border-success/30";
          } else if (isFuture) {
            bubbleClasses +=
              "bg-bg-elevated text-text-muted border border-border-subtle";
          }

          return (
            <div key={index} className="flex items-center">
              <span
                className={bubbleClasses}
                {...(isActive ? { "aria-current": "step" } : {})}
              >
                {index + 1}
              </span>
              {step.description && (
                <span className="ml-1.5 hidden text-xs text-text-muted md:inline">
                  {step.description}
                </span>
              )}
              {index < total - 1 && (
                <span className="mx-2 flex-1 h-px bg-border-subtle" aria-hidden="true" />
              )}
            </div>
          );
        })}
      </div>

      {/* Step body */}
      <div className="mt-4 border border-border-subtle bg-bg-secondary p-4">
        <h2 className="mb-4 flex items-center gap-2 text-base font-bold text-text-primary">
          {currentStepData?.title}
        </h2>
        <div className="space-y-3">{currentStepData?.children}</div>
      </div>

      {/* Footer */}
      <div className="mt-4 flex items-center justify-between">
        {currentStep === 0 ? (
          <span aria-hidden="true" />
        ) : (
          <button
            type="button"
            onClick={handleBack}
            className="text-sm text-text-secondary hover:text-text-primary"
            disabled={isLoading}
          >
            Back
          </button>
        )}

        <button
          type="button"
          onClick={handlePrimary}
          disabled={ctaDisabled}
          aria-disabled={ctaDisabled ? "true" : undefined}
          title={!isValid ? "Complete this step before continuing" : undefined}
          className={
            "bg-accent-cyan text-bg-primary font-bold px-4 py-2 min-h-11 text-sm transition-shadow" +
            (ctaDisabled
              ? " opacity-40 cursor-not-allowed"
              : " hover:glow-cyan")
          }
        >
          {isLoading ? (
            <span
              className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-bg-primary border-t-transparent"
              aria-label="Loading"
            />
          ) : isLastStep ? (
            completeLabel
          ) : (
            "Continue"
          )}
        </button>
      </div>
    </div>
  );
}
