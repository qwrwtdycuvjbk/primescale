import { Reveal, Stagger, StaggerItem } from "./reveal";
import {
  Rocket,
  ShieldCheck,
  Sparkles,
  Users,
  Wallet,
} from "lucide-react";

const features = [
  {
    icon: ShieldCheck,
    title: "Pre-vetted talent",
    body: "Every candidate is screened before they reach you — interview-ready engineers across AI, Cloud, Data, DevOps, and Cybersecurity.",
  },
  {
    icon: Sparkles,
    title: "AI-assisted matching",
    body: "Skill overlap, seniority fit, and LLM scoring surface the right matches for employers and candidates.",
  },
  {
    icon: Users,
    title: "People Prime",
    body: "14+ years of experience and 50,000+ successful deployments. Your staffing backstop with flexible Contract and C2H models.",
  },
  {
    icon: Wallet,
    title: "Payroll & compliance included",
    body: "We handle payroll and compliance end to end — so you focus on hiring great engineers, not back-office overhead.",
  },
  {
    icon: Rocket,
    title: "Onboarding",
    body: "Full onboarding support from offer through start. Sourcing, screening, and ramp-up handled by People Prime.",
  },
];

export function WhyUs() {
  return (
    <section id="why-us" className="bg-background pb-20 sm:pb-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal>
          <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">
            <span className="text-primary">[04]</span>
            <span>Why PrimeScale</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className="display-headline mt-6 max-w-3xl text-balance text-4xl sm:text-6xl">
            Hiring shouldn&apos;t feel like a{" "}
            <span className="italic text-primary">chore.</span>
          </h2>
          <p className="mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground">
            People Prime Worldwide helps companies access pre-vetted, interview-ready
            engineers worldwide. PrimeScale brings that expertise into a platform built for
            both sides.
          </p>
        </Reveal>

        <Stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, i) => (
            <StaggerItem key={feature.title}>
              <div className="group flex h-full flex-col rounded-3xl border border-border bg-card p-7 transition-colors hover:border-primary/50">
                <span className="font-mono text-xs text-primary">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="mt-6 flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-foreground transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                  <feature.icon className="h-6 w-6" />
                </span>
                <h3 className="display-headline mt-auto pt-10 text-2xl">
                  {feature.title}
                </h3>
                <p className="mt-3 text-pretty text-sm leading-relaxed text-muted-foreground">
                  {feature.body}
                </p>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}
