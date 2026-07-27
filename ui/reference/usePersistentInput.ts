/**
 * Reference React hook: debounced localStorage draft for MetaPrompt input.
 *
 * Jest test outline (not executed here):
 * - saves debounced value to localStorage key `metaprompt-draft`
 * - restores value on mount when key exists
 * - clearDraft removes key and resets state
 * - onOptimize callback clears draft before/after optimize
 * - beforeunload writes current value synchronously
 * - skips save for whitespace-only strings
 */

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "metaprompt-draft";
const DEBOUNCE_MS = 400;

function readStoredDraft(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeStoredDraft(text: string): void {
  try {
    if (!text.trim()) {
      localStorage.removeItem(STORAGE_KEY);
      return;
    }
    localStorage.setItem(STORAGE_KEY, text);
  } catch {
    // ignore quota / private mode errors
  }
}

export function clearDraft(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

export interface UsePersistentInputOptions {
  /** Called when user triggers optimize; clears persisted draft. */
  onOptimize?: (text: string) => void | Promise<void>;
  debounceMs?: number;
}

export function usePersistentInput(options: UsePersistentInputOptions = {}) {
  const { onOptimize, debounceMs = DEBOUNCE_MS } = options;
  const [value, setValue] = useState(() => readStoredDraft());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const valueRef = useRef(value);

  useEffect(() => {
    valueRef.current = value;
  }, [value]);

  const persistNow = useCallback((text: string) => {
    writeStoredDraft(text);
  }, []);

  const schedulePersist = useCallback(
    (text: string) => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = setTimeout(() => {
        persistNow(text);
      }, debounceMs);
    },
    [debounceMs, persistNow],
  );

  const handleChange = useCallback(
    (next: string) => {
      setValue(next);
      schedulePersist(next);
    },
    [schedulePersist],
  );

  const handleOptimize = useCallback(async () => {
    const text = valueRef.current.trim();
    if (!text) {
      return;
    }
    clearDraft();
    await onOptimize?.(text);
  }, [onOptimize]);

  useEffect(() => {
    const onBeforeUnload = () => {
      persistNow(valueRef.current);
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [persistNow]);

  return {
    value,
    setValue: handleChange,
    optimize: handleOptimize,
    clearDraft,
    persistNow,
  };
}
