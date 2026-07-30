"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { appContainerClass } from "@/components/site/layout";
import { HeroProductDemo } from "@/components/site/hero-product-demo";

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
  const [value, setValue] = useState(0);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setStarted(true);
          observer.disconnect();
        }
      },
      { rootMargin: "-40px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!started) return;
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
  }, [started, to]);

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
  { value: 24, suffix: "h", label: "To interview-ready matches" },
];

const fadeUp = {
  hidden: { opacity: 0, y: 28 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      delay: 0.08 + i * 0.08,
      duration: 0.65,
      ease: [0.21, 0.47, 0.32, 0.98] as const,
    },
  }),
};

export function Hero() {
  const reduceMotion = useReducedMotion();

  return (
    <section
      id="top"
      className="hero-surface noise relative isolate overflow-hidden bg-ink text-ink-foreground"
    >
      <div className="pointer-events-none absolute inset-0 z-[1]" aria-hidden>
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 90% 70% at 8% 20%, rgba(213, 236, 100, 0.16) 0%, rgba(213, 236, 100, 0.04) 36%, transparent 62%)",
          }}
        />
        <div className="absolute -left-32 top-8 size-[26rem] rounded-full bg-[#d5ec64]/12 blur-3xl" />
        <div className="absolute right-[-8%] top-[22%] size-[20rem] rounded-full bg-[#d5ec64]/4 blur-[100px]" />
      </div>

      <div
        className="pointer-events-none absolute inset-0 z-[2] opacity-[0.035]"
        style={{
          backgroundImage:
            "linear-gradient(to right, currentColor 1px, transparent 1px)",
          backgroundSize: "8.333% 100%",
        }}
      />

      <div
        className={`relative z-10 grid items-start gap-10 pb-10 pt-28 lg:items-center lg:gap-14 lg:pb-14 lg:pt-36 xl:grid-cols-[1.05fr_0.95fr] ${appContainerClass}`}
      >
        <div className="min-w-0 w-full max-w-xl">
          <motion.div
            custom={0}
            variants={fadeUp}
            initial={reduceMotion ? false : "hidden"}
            animate="show"
            className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-ink-muted"
          >
            <span className="text-primary">[01]</span>
            <span>People Remotely</span>
            <span className="h-px flex-1 bg-white/15" />
          </motion.div>

          <h1 className="display-headline mt-5 text-balance text-4xl sm:text-5xl lg:text-[4.35rem]">
            <motion.span
              custom={1}
              variants={fadeUp}
              initial={reduceMotion ? false : "hidden"}
              animate="show"
              className="block"
            >
              Great teams.
            </motion.span>
            <motion.span
              custom={2}
              variants={fadeUp}
              initial={reduceMotion ? false : "hidden"}
              animate="show"
              className="block"
            >
              Great engineers.
            </motion.span>
            <motion.span
              custom={3}
              variants={fadeUp}
              initial={reduceMotion ? false : "hidden"}
              animate="show"
              className="block italic text-primary"
            >
              Finally matched.
            </motion.span>
          </h1>

          <motion.p
            custom={4}
            variants={fadeUp}
            initial={reduceMotion ? false : "hidden"}
            animate="show"
            className="mt-6 max-w-md text-pretty text-base leading-relaxed text-ink-muted sm:text-lg"
          >
            Post a remote tech role. Get recruiter-vetted candidates in 24 hours,
            with payroll, compliance, and onboarding handled.
          </motion.p>

          <motion.div
            custom={5}
            variants={fadeUp}
            initial={reduceMotion ? false : "hidden"}
            animate="show"
            className="mt-8 flex flex-col gap-3 sm:flex-row"
          >
            <Link
              href="/auth/employer/signup"
              className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-primary px-7 py-3.5 text-sm font-semibold text-primary-foreground shadow-[0_0_36px_-10px_rgba(213,236,100,0.65)] transition-transform hover:-translate-y-0.5"
            >
              <span className="absolute inset-0 bg-white/20 opacity-0 transition-opacity group-hover:opacity-100" />
              I&apos;m hiring
              <ArrowRight className="relative h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="/auth/candidate/signup"
              className="group inline-flex items-center justify-center gap-2 rounded-full border border-white/15 px-7 py-3.5 text-sm font-semibold text-ink-foreground transition-colors hover:bg-white/5"
            >
              I&apos;m a candidate
              <ArrowUpRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </Link>
          </motion.div>
        </div>

        <div className="min-w-0 w-full xl:pl-2">
          <HeroProductDemo />
        </div>
      </div>

      <div className={`relative z-10 pb-12 ${appContainerClass}`}>
        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.6, ease: [0.21, 0.47, 0.32, 0.98] }}
          className="grid grid-cols-1 divide-y divide-white/10 border-y border-white/10 sm:grid-cols-3 sm:divide-x sm:divide-y-0"
        >
          {stats.map((stat, i) => (
            <div
              key={stat.label}
              className="flex items-baseline gap-3 py-5 sm:px-5 first:sm:pl-0"
            >
              <span className="font-mono text-xs text-primary">0{i + 1}</span>
              <div>
                <div className="display-headline text-3xl text-ink-foreground sm:text-4xl">
                  <Counter to={stat.value} suffix={stat.suffix} />
                </div>
                <p className="mt-1 text-sm text-ink-muted">{stat.label}</p>
              </div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
