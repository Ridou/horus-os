import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Stepper } from "../Stepper";
import type { StepperStep } from "../Stepper";

const steps: StepperStep[] = [
  { title: "First Step", children: <p>Step one content</p> },
  { title: "Second Step", children: <p>Step two content</p> },
  { title: "Third Step", children: <p>Step three content</p> },
];

describe("Stepper", () => {
  it("hides the Back button on step 0", () => {
    render(
      <Stepper
        steps={steps}
        currentStep={0}
        onStepChange={vi.fn()}
        onComplete={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /back/i })).not.toBeInTheDocument();
  });

  it("shows Back button on step > 0 and clicking it calls onStepChange with currentStep - 1", async () => {
    const onStepChange = vi.fn();
    render(
      <Stepper
        steps={steps}
        currentStep={1}
        onStepChange={onStepChange}
        onComplete={vi.fn()}
      />,
    );
    const backBtn = screen.getByRole("button", { name: /back/i });
    expect(backBtn).toBeInTheDocument();
    await userEvent.click(backBtn);
    expect(onStepChange).toHaveBeenCalledWith(0);
  });

  it("disables Continue when isValid is false and clicking it does not call onStepChange", async () => {
    const onStepChange = vi.fn();
    const invalidSteps: StepperStep[] = [
      { title: "Invalid Step", isValid: false, children: <p>Content</p> },
      { title: "Second Step", children: <p>Content</p> },
    ];
    render(
      <Stepper
        steps={invalidSteps}
        currentStep={0}
        onStepChange={onStepChange}
        onComplete={vi.fn()}
      />,
    );
    const continueBtn = screen.getByRole("button", { name: /continue/i });
    expect(continueBtn).toBeDisabled();
    expect(continueBtn).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(continueBtn);
    expect(onStepChange).not.toHaveBeenCalled();
  });

  it("calls onStepChange with currentStep + 1 when Continue is clicked on a valid non-last step", async () => {
    const onStepChange = vi.fn();
    render(
      <Stepper
        steps={steps}
        currentStep={0}
        onStepChange={onStepChange}
        onComplete={vi.fn()}
      />,
    );
    const continueBtn = screen.getByRole("button", { name: /continue/i });
    await userEvent.click(continueBtn);
    expect(onStepChange).toHaveBeenCalledWith(1);
  });

  it("calls onComplete (not onStepChange) when the final step button is clicked", async () => {
    const onStepChange = vi.fn();
    const onComplete = vi.fn();
    const lastIndex = steps.length - 1;
    render(
      <Stepper
        steps={steps}
        currentStep={lastIndex}
        onStepChange={onStepChange}
        onComplete={onComplete}
      />,
    );
    const finishBtn = screen.getByRole("button", { name: /finish setup/i });
    expect(finishBtn).toBeInTheDocument();
    await userEvent.click(finishBtn);
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onStepChange).not.toHaveBeenCalled();
  });
});
