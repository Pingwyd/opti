/**
 * Reference-only React/Tailwind component mirroring MetaPrompt's pill bar aesthetic.
 * The production app is PyQt6; this file is for design docs and cross-platform alignment.
 */
import { Sparkles } from "lucide-react";
import { useState } from "react";

const TOKENS = {
  bg: "bg-zinc-950/90",
  border: "border-white/10",
  borderFocus: "border-[#F08060]/40",
  text: "text-zinc-100",
  placeholder: "text-zinc-500",
  accent: "text-[#F08060]",
} as const;

type AgentPillProps = {
  value?: string;
  placeholder?: string;
  busy?: boolean;
  onChange?: (value: string) => void;
  onSubmit?: (value: string) => void;
};

export function AgentPill({
  value = "",
  placeholder = "What can I help you with today?",
  busy = false,
  onChange,
  onSubmit,
}: AgentPillProps) {
  const [focused, setFocused] = useState(false);

  return (
    <div
      className={[
        "flex w-full max-w-xl items-center gap-3 rounded-full px-5 py-3 backdrop-blur-md transition-colors",
        TOKENS.bg,
        focused ? TOKENS.borderFocus : TOKENS.border,
        "border hover:border-white/20",
      ].join(" ")}
    >
      <Sparkles className={`h-5 w-5 shrink-0 ${TOKENS.accent}`} aria-hidden />
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        disabled={busy}
        aria-label="Prompt input"
        onChange={(e) => onChange?.(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit?.(value);
          }
        }}
        className={[
          "min-w-0 flex-1 bg-transparent text-sm outline-none",
          TOKENS.text,
          `placeholder:${TOKENS.placeholder}`,
        ].join(" ")}
      />
      {busy ? (
        <span className={`text-sm ${TOKENS.accent}`} aria-live="polite">
          ...
        </span>
      ) : null}
    </div>
  );
}

export default AgentPill;
