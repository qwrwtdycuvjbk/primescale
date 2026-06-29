"use client";

import Link from "next/link";
import { motion, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, Check } from "lucide-react";

function Counter({
  to,
  suffix = "",
  prefix = "",
}: {
  to: number;
  suffix?: string;
  prefix?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let raf = 0;
    const start = performance.now();
    const duration = 1400;
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Math.round(eased * to));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to]);

  return (
    <span ref={ref}>
      {prefix}
      {value.toLocaleString()}
      {suffix}
    </span>
  );
}

const stats = [
  { value: 14, suffix: "+", label: "Years of staffing experience" },
  { value: 50000, suffix: "+", label: "Successful deployments" },
  { value: 24, suffix: "h", label: "To matched, interview-ready talent" },
];

const ease = [0.21, 0.47, 0.32, 0.98] as const;

export function Hero() {
  return (
    <section
      id="top"
      className="noise relative overflow-hidden bg-ink text-ink-foreground"
    >
      <div className="pointer-events-none absolute -left-40 top-0 h-[28rem] w-[28rem] rounded-full bg-primary/20 blur-[130px]" />
      <div className="pointer-events-none absolute right-0 top-1/3 h-80 w-80 rounded-full bg-primary/10 blur-[130px]" />

      <div
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(to right, currentColor 1px, transparent 1px)",
          backgroundSize: "8.333% 100%",
        }}
      />

      <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 pb-16 pt-36 sm:px-6 lg:grid-cols-12 lg:gap-8 lg:pt-44 lg:pb-20">
        <div className="lg:col-span-7">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease }}
            className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-ink-muted"
          >
            <span className="text-primary">[01]</span>
            <span>US remote tech hiring</span>
            <span className="h-px flex-1 bg-white/15" />
          </motion.div>

          <h1 className="display-headline mt-6 text-balance text-[3.25rem] sm:text-7xl lg:text-[5.5rem]">
            <motion.span
              className="block"
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.05, ease }}
            >
              Great teams.
            </motion.span>
            <motion.span
              className="block"
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.13, ease }}
            >
              Great engineers.
            </motion.span>
            <motion.span
              className="block italic text-primary"
              style={{ fontVariationSettings: "'WONK' 1, 'SOFT' 40" }}
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.21, ease }}
            >
              Finally matched.
            </motion.span>
          </h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.32, ease }}
            className="mt-7 max-w-xl text-pretty text-lg leading-relaxed text-ink-muted"
          >
            PrimeScale is an AI hiring platform for US remote tech roles. Employers
            post roles. Candidates build a profile. Our matching engine connects
            both sides, backed by People Prime Worldwide.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.42, ease }}
            className="mt-9 flex flex-col gap-3 sm:flex-row"
          >
            <Link
              href="/auth/signup?role=employer"
              className="group inline-flex items-center justify-center gap-2 rounded-full bg-primary px-7 py-4 text-base font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
            >
              I&apos;m hiring
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="/auth/signup?role=candidate"
              className="group inline-flex items-center justify-center gap-2 rounded-full border border-white/15 px-7 py-4 text-base font-semibold text-ink-foreground transition-colors hover:bg-white/5"
            >
              I&apos;m a candidate
              <ArrowUpRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </Link>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 30, rotate: -2 }}
          animate={{ opacity: 1, y: 0, rotate: 0 }}
          transition={{ duration: 0.7, delay: 0.3, ease }}
          className="relative lg:col-span-5"
        >
          <div className="absolute -right-2 -top-4 hidden h-full w-full rotate-3 rounded-3xl border border-white/10 bg-white/[0.03] lg:block" />

          <div className="relative rounded-3xl border border-white/10 bg-white/[0.06] p-6 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">
                New match
              </span>
              <span className="flex items-center gap-1.5 rounded-full bg-primary/15 px-2.5 py-1 text-xs font-semibold text-primary">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
                </span>
                92% fit
              </span>
            </div>

            <div className="mt-5 flex items-center gap-4">
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary font-display text-2xl font-semibold text-primary-foreground">
                AK
              </span>
              <div>
                <p className="text-lg font-semibold">Alex Kumar</p>
                <p className="text-sm text-ink-muted">Senior DevOps Engineer</p>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              {[
                "Remote · US",
                "$140k–$175k",
                "AWS",
                "Kubernetes",
                "Terraform",
              ].map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-ink-foreground"
                >
                  {tag}
                </span>
              ))}
            </div>

            <div className="mt-6 space-y-2.5 border-t border-white/10 pt-5">
              {[
                "Pre-vetted by People Prime",
                "Open to contract or C2H",
                "Matched to your tech stack",
              ].map((line, i) => (
                <motion.div
                  key={line}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4, delay: 0.7 + i * 0.12, ease }}
                  className="flex items-center gap-2.5 text-sm text-ink-muted"
                >
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20 text-primary">
                    <Check className="h-3 w-3" />
                  </span>
                  {line}
                </motion.div>
              ))}
            </div>

            <button
              type="button"
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-full bg-white/10 py-3 text-sm font-semibold text-ink-foreground transition-colors hover:bg-white/15"
            >
              View match
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.6, ease }}
        className="relative mx-auto max-w-7xl px-4 pb-16 sm:px-6"
      >
        <div className="grid grid-cols-1 divide-y divide-white/10 border-y border-white/10 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {stats.map((stat, i) => (
            <div
              key={stat.label}
              className="flex items-baseline gap-4 py-6 sm:px-6 first:sm:pl-0"
            >
              <span className="font-mono text-xs text-primary">0{i + 1}</span>
              <div>
                <div className="display-headline text-4xl text-ink-foreground sm:text-5xl">
                  <Counter to={stat.value} suffix={stat.suffix} />
                </div>
                <p className="mt-1 text-sm text-ink-muted">{stat.label}</p>
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </section>
  );
}
