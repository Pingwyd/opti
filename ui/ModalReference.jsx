/**
 * Reference React modal — same UX patterns as MetaPrompt's vanilla UI.
 * Use if you port the popup to React; not wired into the pywebview app today.
 */
import { useCallback, useEffect, useId, useRef } from "react";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

type CenteredPromptModalProps = {
  open: boolean;
  title: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onClose: () => void;
  children?: React.ReactNode;
};

export function CenteredPromptModal({
  open,
  title,
  placeholder = "What do you want to ask an AI?",
  value,
  onChange,
  onSubmit,
  onClose,
  children,
}: CenteredPromptModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const titleId = useId();
  const descId = useId();

  const trapFocus = useCallback((e: KeyboardEvent) => {
    const root = dialogRef.current;
    if (!root || e.key !== "Tab") return;

    const nodes = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => !el.hasAttribute("disabled")
    );
    if (!nodes.length) return;

    const first = nodes[0];
    const last = nodes[nodes.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }, []);

  useEffect(() => {
    if (!open) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    // Blur dismiss: only when the whole window loses focus (not inner clicks)
    const onWindowBlur = () => {
      window.setTimeout(() => {
        if (!document.hasFocus()) onClose();
      }, 140);
    };

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keydown", trapFocus);
    window.addEventListener("blur", onWindowBlur);
    inputRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("keydown", trapFocus);
      window.removeEventListener("blur", onWindowBlur);
    };
  }, [open, onClose, trapFocus]);

  if (!open) return null;

  return (
    <div className="shell" role="presentation">
      <section
        ref={dialogRef}
        className="dialog dialog--main"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
      >
        <div className="input-bar">
          <span className="visually-hidden" id={titleId}>
            {title}
          </span>
          <textarea
            ref={inputRef}
            className="input-bar__input"
            rows={1}
            placeholder={placeholder}
            value={value}
            aria-describedby={descId}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSubmit();
              }
            }}
          />
        </div>
        <p id={descId} className="visually-hidden">
          Press Enter to submit. Press Escape or click outside to close.
        </p>
        {children}
      </section>
    </div>
  );
}
