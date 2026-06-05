import { useSyncExternalStore } from "react";

/** Matches the Tailwind `md` breakpoint where the sidebar becomes persistent. */
const QUERY = "(min-width: 768px)";

function subscribe(callback: () => void) {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return () => {};
  }
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getSnapshot() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(QUERY).matches;
}

function getServerSnapshot() {
  return false;
}

/**
 * True at the md breakpoint and up, where the sidebar is a persistent column.
 * Defaults to false (mobile) during static export, server rendering, and in
 * environments without matchMedia (jsdom), which is the safe default for the
 * off-canvas drawer: a closed drawer is treated as collapsed until proven
 * otherwise. Reads the value during render via useSyncExternalStore, so it
 * needs no effect and stays clean under the React Compiler hooks rules.
 */
export function useIsDesktop() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
