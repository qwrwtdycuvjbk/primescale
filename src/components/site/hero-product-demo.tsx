"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Check, FileText, UserCheck } from "lucide-react";

type Phase = "post" | "match" | "select" | "onboard";

const candidates = [
  {
    initials: "AK",
    name: "Alex Kumar",
    role: "Senior DevOps Engineer",
    tags: ["AWS", "Kubernetes", "Terraform"],
    fit: 96,
  },
  {
    initials: "MR",
    name: "Maya Reyes",
    role: "Staff Backend Engineer",
    tags: ["Go", "Postgres", "gRPC"],
    fit: 94,
  },
  {
    initials: "JL",
    name: "Jordan Lee",
    role: "Senior Full-stack",
    tags: ["React", "Node", "Remote"],
    fit: 91,
  },
];

const phaseMeta: Record<
  Phase,
  { label: string; detail: string; progress: number; nav: number; step: number }
> = {
  post: {
    label: "Posting role",
    detail: "JD parsed · publishing role",
    progress: 22,
    nav: 0,
    step: 0,
  },
  match: {
    label: "Matching",
    detail: "Recruiter-reviewed shortlist building",
    progress: 58,
    nav: 1,
    step: 1,
  },
  select: {
    label: "Select hire",
    detail: "Choose who to move forward",
    progress: 80,
    nav: 2,
    step: 2,
  },
  onboard: {
    label: "Onboarding",
    detail: "Payroll, compliance, and onboarding",
    progress: 100,
    nav: 3,
    step: 3,
  },
};

const steps = ["Post", "Match", "Select", "Onboard"];
const navItems = ["Roles", "Matches", "Shortlist", "Onboarding"];

export function HeroProductDemo() {
  const reduceMotion = useReducedMotion();
  const [started, setStarted] = useState(false);
  const [loopKey, setLoopKey] = useState(0);
  const [phase, setPhase] = useState<Phase>("post");
  const [visibleCount, setVisibleCount] = useState(0);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  useEffect(() => {
    if (reduceMotion) {
      setStarted(true);
      setPhase("onboard");
      setVisibleCount(candidates.length);
      setSelectedIndex(0);
      return;
    }

    let cancelled = false;
    const timers: number[] = [];
    const wait = (ms: number, fn: () => void) => {
      timers.push(
        window.setTimeout(() => {
          if (!cancelled) fn();
        }, ms),
      );
    };

    const runLoop = () => {
      if (cancelled) return;
      setLoopKey((k) => k + 1);
      setPhase("post");
      setVisibleCount(0);
      setSelectedIndex(null);

      // Match: cards fade in like Onboard, a bit slower
      wait(2800, () => {
        setPhase("match");
        setVisibleCount(candidates.length);
      });

      // Hold the shortlist, then select
      wait(7800, () => setPhase("select"));
      wait(9000, () => setSelectedIndex(0));

      wait(10800, () => setPhase("onboard"));

      wait(15500, runLoop);
    };

    wait(1800, () => {
      setStarted(true);
      runLoop();
    });

    return () => {
      cancelled = true;
      timers.forEach((id) => window.clearTimeout(id));
    };
  }, [reduceMotion]);

  const meta = phaseMeta[phase];
  const playMotion = !reduceMotion && started;

  return (
    <motion.div
      className="relative w-full min-w-0"
      initial={reduceMotion ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: [0.21, 0.47, 0.32, 0.98], delay: 0.45 }}
    >
      <div className="relative flex h-[520px] w-full min-w-0 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#101418]/90 shadow-[0_24px_50px_-24px_rgba(0,0,0,0.7)] sm:h-[540px]">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-white/10 px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex shrink-0 items-center gap-1.5">
              <span className="size-1.5 rounded-full bg-white/20" />
              <span className="size-1.5 rounded-full bg-white/20" />
              <span className="size-1.5 rounded-full bg-white/20" />
            </div>
            <span className="truncate font-mono text-[10px] uppercase tracking-[0.2em] text-ink-muted">
              primescale.io
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-ink-muted">
            <span className="size-1.5 rounded-full bg-primary" />
            Live
          </div>
        </div>

        <div className="grid min-h-0 min-w-0 flex-1 xl:grid-cols-[120px_minmax(0,1fr)]">
          <aside className="hidden border-r border-white/10 bg-white/[0.03] p-3.5 xl:block">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-muted">
              Workspace
            </p>
            <div className="mt-3 space-y-1">
              {navItems.map((item, i) => (
                <div
                  key={item}
                  className={`rounded-lg px-2.5 py-2 text-xs transition-colors duration-300 ${
                    i === meta.nav
                      ? "bg-primary text-primary-foreground"
                      : "text-ink-muted"
                  }`}
                >
                  {item}
                </div>
              ))}
            </div>
          </aside>

          <div className="flex min-h-0 min-w-0 flex-col overflow-hidden bg-[#f4f5f2] p-4 text-[#171a1c] sm:p-5">
            <div className="mb-3 flex shrink-0 gap-1">
              {steps.map((step, i) => {
                const active = i === meta.step;
                const done = i < meta.step;
                return (
                  <div
                    key={step}
                    className={`flex flex-1 items-center justify-center gap-1 rounded-full border px-1.5 py-1 text-[10px] font-medium transition-colors duration-500 sm:gap-1.5 sm:px-2 sm:text-[11px] ${
                      active
                        ? "border-[#101418]/15 bg-[#101418] text-white"
                        : done
                          ? "border-[#101418]/10 bg-white text-[#171a1c]"
                          : "border-[#101418]/8 bg-white/70 text-[#6b7280]"
                    }`}
                  >
                    {done ? (
                      <Check className="size-3 text-[#101418]" strokeWidth={3} />
                    ) : (
                      <span className="font-mono">0{i + 1}</span>
                    )}
                    <span className="hidden sm:inline">{step}</span>
                  </div>
                );
              })}
            </div>

            <div className="flex shrink-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.22em] text-[#6b7280]">
                  <span className="text-[#4d6b00]">[01]</span>
                  <span>{phase === "post" ? "New role" : "Open role"}</span>
                </div>
                <h3 className="display-headline mt-1.5 truncate text-lg text-[#171a1c] sm:text-xl">
                  Senior DevOps
                </h3>
                <p className="mt-1 truncate text-xs text-[#6b7280]">
                  US remote · Contract / C2H · $140k–$175k
                </p>
              </div>
              <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-[#101418]/10 bg-white px-3 py-1.5 text-[11px] font-medium text-[#4d6b00]">
                <span className="size-1.5 rounded-full bg-primary" />
                {meta.label}
              </span>
            </div>

            <div className="mt-3 shrink-0">
              <div className="mb-1.5 flex items-center justify-between gap-3 text-[11px]">
                <span className="truncate text-[#6b7280]">{meta.detail}</span>
                <span className="shrink-0 font-mono text-[#4d6b00]">
                  {meta.progress}%
                </span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-[#101418]/10">
                <motion.div
                  className="h-full rounded-full bg-primary"
                  animate={{ width: `${meta.progress}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                />
              </div>
            </div>

            <div className="mt-3 min-h-0 flex-1 overflow-hidden">
              <AnimatePresence mode="wait" initial={false}>
                {phase === "post" ? (
                  <motion.div
                    key={`post-${loopKey}`}
                    initial={playMotion ? { opacity: 0 } : false}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.25 }}
                    className="h-full"
                  >
                    <div className="flex h-full flex-col rounded-2xl border border-[#101418]/10 bg-white p-3.5 shadow-sm">
                      <div className="mb-2.5 flex shrink-0 items-center gap-2.5">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                          <FileText className="size-4" />
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-[#171a1c]">
                            Post a role for free
                          </p>
                          <p className="truncate text-xs text-[#6b7280]">
                            Paste a JD. We handle the rest.
                          </p>
                        </div>
                      </div>

                      <div className="flex shrink-0 flex-col gap-2">
                        {[
                          { label: "Title", value: "Senior DevOps Engineer" },
                          {
                            label: "Stack",
                            value: "AWS · Kubernetes · Terraform",
                          },
                        ].map((row, i) => (
                          <motion.div
                            key={row.label}
                            initial={playMotion ? { opacity: 0 } : false}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.2 + i * 0.3, duration: 0.3 }}
                            className="rounded-xl border border-[#101418]/8 bg-[#f4f5f2] px-3 py-2"
                          >
                            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6b7280]">
                              {row.label}
                            </p>
                            <p className="mt-1 truncate text-sm font-medium leading-snug text-[#171a1c]">
                              {row.value}
                            </p>
                          </motion.div>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                ) : phase === "onboard" ? (
                  <motion.div
                    key="onboard"
                    initial={reduceMotion ? false : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.25 }}
                    className="flex h-full flex-col gap-3"
                  >
                    <div className="flex shrink-0 items-center gap-3 rounded-2xl border border-primary/40 bg-primary/25 px-3 py-3">
                      <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary font-display text-sm font-semibold text-primary-foreground">
                        AK
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-[#171a1c]">
                          Alex Kumar selected
                        </p>
                        <p className="truncate text-xs text-[#6b7280]">
                          People Prime starts onboarding
                        </p>
                      </div>
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#101418]/10 bg-white text-[#4d6b00]">
                        <UserCheck className="size-4" />
                      </span>
                    </div>

                    <div className="min-h-0 flex-1 overflow-hidden rounded-2xl border border-[#101418]/10 bg-white px-3 shadow-sm">
                      {[
                        { label: "Offer & contract", status: "Done" },
                        { label: "Payroll setup", status: "Done" },
                        { label: "Compliance checks", status: "Done" },
                      ].map((step, i) => (
                        <motion.div
                          key={step.label}
                          initial={reduceMotion ? false : { opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: 0.15 + i * 0.2, duration: 0.35 }}
                          className="flex items-center justify-between gap-3 border-b border-[#101418]/8 py-3 last:border-b-0"
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/25 font-mono text-[10px] text-[#4d6b00]">
                              0{i + 1}
                            </span>
                            <span className="truncate text-sm text-[#171a1c]">
                              {step.label}
                            </span>
                          </div>
                          <span className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-[#4d6b00]">
                            <span className="flex size-4 items-center justify-center rounded-full bg-primary/30 text-[#4d6b00]">
                              <Check className="size-2.5" strokeWidth={3} />
                            </span>
                            Done
                          </span>
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                ) : (
                  <motion.div
                    key={`list-${loopKey}`}
                    initial={reduceMotion ? false : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.25 }}
                    className="flex h-full flex-col gap-2"
                  >
                    {candidates.map((person, index) => {
                      const selected = selectedIndex === index;
                      const dimmed =
                        phase === "select" &&
                        selectedIndex !== null &&
                        !selected;

                      return (
                        <motion.div
                          key={person.name}
                          initial={reduceMotion ? false : { opacity: 0 }}
                          animate={{ opacity: dimmed ? 0.4 : 1 }}
                          transition={{
                            delay:
                              phase === "match" && playMotion
                                ? 0.25 + index * 0.55
                                : 0,
                            duration: 0.45,
                          }}
                          className={`flex min-h-0 flex-1 items-center gap-3 overflow-hidden rounded-2xl border px-3.5 py-2.5 transition-[border-color,background-color,box-shadow] duration-500 ${
                            selected
                              ? "border-primary bg-primary/15 shadow-sm"
                              : "border-[#101418]/8 bg-white shadow-sm"
                          }`}
                        >
                          <div className="relative flex size-9 shrink-0 items-center justify-center rounded-full bg-primary font-display text-sm font-semibold text-primary-foreground">
                            {person.initials}
                            {selected && (
                              <span className="absolute -bottom-0.5 -right-0.5 flex size-4 items-center justify-center rounded-full border-2 border-white bg-[#101418] text-white">
                                <Check className="size-2.5" strokeWidth={3} />
                              </span>
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-semibold leading-tight tracking-tight text-[#171a1c]">
                              {person.name}
                            </p>
                            <p className="mt-0.5 truncate text-xs leading-tight text-[#6b7280]">
                              {person.role}
                            </p>
                            <div className="mt-1.5 flex flex-wrap gap-1">
                              {person.tags.map((tag) => (
                                <span
                                  key={tag}
                                  className="rounded-full border border-[#101418]/8 bg-[#f4f5f2] px-2 py-0.5 text-[10px] leading-none text-[#6b7280]"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                          <div className="flex w-11 shrink-0 flex-col items-center justify-center">
                            <p className="display-headline text-[1.15rem] leading-none tabular-nums text-[#4d6b00]">
                              {person.fit}%
                            </p>
                            <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.16em] text-[#6b7280]">
                              {selected ? "hired" : "fit"}
                            </p>
                          </div>
                        </motion.div>
                      );
                    })}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="mt-3 grid shrink-0 grid-cols-3 gap-2 border-t border-[#101418]/10 pt-3">
              {[
                { label: "Payroll", done: phase === "onboard", idle: "Queued" },
                {
                  label: "Compliance",
                  done: phase === "onboard",
                  idle: "Queued",
                },
                {
                  label: "Onboarding",
                  done: phase === "onboard",
                  idle: "Waiting",
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className={`min-w-0 rounded-xl border px-2 py-2 text-center transition-colors duration-500 ${
                    item.done
                      ? "border-primary/50 bg-primary/20"
                      : "border-[#101418]/8 bg-white"
                  }`}
                >
                  <p className="truncate font-mono text-[10px] uppercase tracking-[0.14em] text-[#6b7280]">
                    {item.label}
                  </p>
                  <p
                    className={`mt-1 truncate text-xs font-medium ${
                      item.done ? "text-[#4d6b00]" : "text-[#6b7280]"
                    }`}
                  >
                    {item.done ? "Handled" : item.idle}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
