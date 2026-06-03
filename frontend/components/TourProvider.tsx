"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

const TOUR_KEY = "horus_tour_completed";

export interface TourStep {
  step: number;
  path: string;
  title: string;
  copy: string;
}

export const TOUR_STEPS: TourStep[] = [
  {
    step: 1,
    path: "/",
    title: "Welcome",
    copy: "Welcome to horus-os, your self-hosted AI command center. A team of agents works for you on your own machine, and every action is traceable. Here is a quick tour.",
  },
  {
    step: 2,
    path: "/team",
    title: "Your team",
    copy: "Your team. A Coordinator routes each request to the right specialist: Engineer, Researcher, Writer, and Operator. Click any agent to read its persona and recent runs.",
  },
  {
    step: 3,
    path: "/memory",
    title: "The memory vault",
    copy: "The memory vault. Your agents read and write plain markdown notes here. Edit them in any editor, including Obsidian, and every write is logged.",
  },
  {
    step: 4,
    path: "/tasks",
    title: "Tasks",
    copy: "Tasks. See what the team is working on or has queued, filter by status, and cancel or retry any task.",
  },
  {
    step: 5,
    path: "/research",
    title: "Autonomous research",
    copy: "Autonomous research. Give the team a question and it plans the work, gathers and cites sources, and writes a report straight into your vault.",
  },
  {
    step: 6,
    path: "/activity",
    title: "Activity feed",
    copy: "Activity. A live feed of everything your agents do, streamed as it happens.",
  },
  {
    step: 7,
    path: "/traces",
    title: "Traces",
    copy: "Traces. Open any run to see its exact prompt, model, tool calls, cost, and child runs. Nothing the agents do is hidden.",
  },
  {
    step: 8,
    path: "/costs",
    title: "Costs and observability",
    copy: "Costs and observability. Track spend, token usage, latency, and tool reliability across every provider.",
  },
  {
    step: 9,
    path: "/integrations",
    title: "Integrations",
    copy: "Integrations. Connect Discord, Slack, Email, Calendar, and more. Every integration is opt-in and uses your own keys.",
  },
  {
    step: 10,
    path: "/about",
    title: "You are all set",
    copy: "That is the tour. Open Settings to add your provider keys, and replay this tour any time from the About page. Now hand your team a goal.",
  },
];

interface TourContextValue {
  isTourActive: boolean;
  currentStep: number;
  totalSteps: number;
  startTour: () => void;
  skipTour: () => void;
  nextStep: () => void;
  prevStep: () => void;
}

const TourContext = createContext<TourContextValue | null>(null);

export function TourProvider({ children }: { children: ReactNode }) {
  const [isTourActive, setIsTourActive] = useState(false);
  const [step, setStep] = useState(0);
  const router = useRouter();

  // Auto-start on first run (SSR guard matches use-tab-param pattern)
  useEffect(() => {
    if (typeof window !== "undefined" && !localStorage.getItem(TOUR_KEY)) {
      setIsTourActive(true);
    }
  }, []);

  const startTour = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOUR_KEY);
    }
    setStep(0);
    setIsTourActive(true);
  }, []);

  const skipTour = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(TOUR_KEY, "1");
    }
    setIsTourActive(false);
  }, []);

  const nextStep = useCallback(() => {
    const nextIndex = step + 1;
    if (nextIndex >= TOUR_STEPS.length) {
      // Last step - done
      if (typeof window !== "undefined") {
        localStorage.setItem(TOUR_KEY, "1");
      }
      setIsTourActive(false);
      return;
    }
    const nextPath = TOUR_STEPS[nextIndex].path;
    try {
      router.push(nextPath);
    } catch {
      // Navigation failure - silently advance per UI-SPEC
    }
    setStep(nextIndex);
  }, [step, router]);

  const prevStep = useCallback(() => {
    if (step <= 0) return;
    const prevIndex = step - 1;
    const prevPath = TOUR_STEPS[prevIndex].path;
    try {
      router.push(prevPath);
    } catch {
      // Navigation failure - silently move back
    }
    setStep(prevIndex);
  }, [step, router]);

  return (
    <TourContext.Provider
      value={{
        isTourActive,
        currentStep: step,
        totalSteps: TOUR_STEPS.length,
        startTour,
        skipTour,
        nextStep,
        prevStep,
      }}
    >
      {children}
    </TourContext.Provider>
  );
}

export function useTour(): TourContextValue {
  const ctx = useContext(TourContext);
  if (!ctx) throw new Error("useTour must be used inside TourProvider");
  return ctx;
}
