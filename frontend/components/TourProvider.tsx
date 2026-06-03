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
    copy: "Welcome to horus-os. This is your command center. See what your agents have been up to at a glance.",
  },
  {
    step: 2,
    path: "/team",
    title: "Your team",
    copy: "Your starter team. Five agents are ready to work. Click any card to inspect its soul and traces.",
  },
  {
    step: 3,
    path: "/memory",
    title: "Memory vault",
    copy: "The memory vault. Everything your agents read and write lives here as plain markdown files.",
  },
  {
    step: 4,
    path: "/activity",
    title: "Activity feed",
    copy: "Activity feed. Every action your agents take streams here in real time.",
  },
  {
    step: 5,
    path: "/about",
    title: "Tour complete",
    copy: "That is the tour. You can replay it any time from this page.",
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
