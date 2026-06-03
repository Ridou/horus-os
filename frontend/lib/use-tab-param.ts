"use client";

import { useRouter, usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

/*
 * Patch history.pushState / replaceState once so that <Link> navigations
 * (which do not fire popstate) still notify listeners of URL changes. Without
 * this, clicking a Link that only changes a query param updates the URL but
 * leaves every useTabParam hook stale.
 */
type PatchedWindow = Window & { __horusHistoryPatched?: boolean };

if (typeof window !== "undefined" && !(window as PatchedWindow).__horusHistoryPatched) {
  (window as PatchedWindow).__horusHistoryPatched = true;
  const origPush = window.history.pushState.bind(window.history);
  const origReplace = window.history.replaceState.bind(window.history);
  const fire = () => window.dispatchEvent(new CustomEvent("horus:params-changed"));
  window.history.pushState = function patchedPushState(...args) {
    const ret = origPush(...(args as Parameters<typeof origPush>));
    fire();
    return ret;
  };
  window.history.replaceState = function patchedReplaceState(...args) {
    const ret = origReplace(...(args as Parameters<typeof origReplace>));
    fire();
    return ret;
  };
}

/**
 * Sync a tab / selection state with a URL search param.
 *
 * Reads from window.location rather than useSearchParams so the page does not
 * need a Suspense boundary (which would break static export). The value is
 * always initialized to the default so the first client render is stable,
 * then synced from the URL on mount.
 *
 * @param paramName    URL search param name (default "tab").
 * @param defaultValue value used when the param is absent.
 * @returns [value, setValue] drop-in replacement for useState.
 */
export function useTabParam<T extends string>(
  paramName = "tab",
  defaultValue: T = "" as T,
): [T, (value: T) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const [value, setValue] = useState<T>(defaultValue);

  useEffect(() => {
    const syncFromUrl = () => {
      if (typeof window === "undefined") return;
      const current = new URL(window.location.href).searchParams.get(
        paramName,
      ) as T | null;
      setValue(current !== null ? current : defaultValue);
    };
    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    window.addEventListener("horus:params-changed", syncFromUrl);
    return () => {
      window.removeEventListener("popstate", syncFromUrl);
      window.removeEventListener("horus:params-changed", syncFromUrl);
    };
  }, [pathname, paramName, defaultValue]);

  const setValueAndUrl = useCallback(
    (next: T) => {
      setValue(next);
      const url = new URL(window.location.href);
      if (next === defaultValue || next === "") {
        url.searchParams.delete(paramName);
      } else {
        url.searchParams.set(paramName, next);
      }
      const qs = url.searchParams.toString();
      router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [pathname, router, paramName, defaultValue],
  );

  return [value, setValueAndUrl];
}
