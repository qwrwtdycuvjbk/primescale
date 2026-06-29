import { Reveal, Stagger, StaggerItem } from "./reveal";
import { Gauge, ShieldCheck, Sparkles, Users } from "lucide-react";

const features = [
  {
    icon: Gauge,
    title: "Fast by design",
    body: "Smart matching means less time sorting résumés and more time talking to the right people. Matched talent in as little as 24 hours.",
    big: true,
  },
  {
    icon: ShieldCheck,
    title: "Pre-vetted talent",
    body: "Every candidate is screened before they reach you. Interview-ready engineers across AI, Cloud, Data, DevOps, and Cybersecurity.",
  },
  {
    icon: Sparkles,
    title: "AI-assisted matching",
    body: "Skill overlap, seniority fit, and LLM scoring surface the right matches for employers and candidates.",
  },
  {
    icon: Users,
    title: "People Prime backstop",
    body: "14+ years of staffing experience, 50,000+ deployments, and full lifecycle support from sourcing to onboarding.",
  },
];

export function WhyUs() {
  return (
    <section id="why-us" className="bg-background pb-20 sm:pb-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal>
          <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">
            <span className="text-primary">[03]</span>
            <span>Why PrimeScale</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className="display-headline mt-6 max-w-3xl text-balance text-4xl sm:text-6xl">
            Hiring shouldn&apos;t feel like a{" "}
            <span className="italic text-primary">chore.</span>
          </h2>
          <p className="mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground">
            People Prime Worldwide helps US companies access pre-vetted, interview-ready
            engineers. PrimeScale brings that expertise into an AI platform built for
            both sides.
          </p>
        </Reveal>

        <Stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, i) => (
            <StaggerItem
              key={feature.title}
              className={feature.big ? "lg:col-span-1 lg:row-span-2" : ""}
            >
              <div
                className={`group relative flex h-full flex-col overflow-hidden rounded-3xl border border-border bg-card p-7 transition-colors hover:border-primary/50 ${
                  feature.big ? "lg:bg-ink lg:text-ink-foreground" : ""
                }`}
              >
                <span className="font-mono text-xs text-primary">0{i + 1}</span>
                <span
                  className={`mt-6 flex h-12 w-12 items-center justify-center rounded-xl transition-colors ${
                    feature.big
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground group-hover:bg-primary group-hover:text-primary-foreground"
                  }`}
                >
                  <feature.icon className="h-6 w-6" />
                </span>
                <h3
                  className={`display-headline mt-auto pt-10 ${
                    feature.big ? "text-3xl sm:text-4xl" : "text-2xl"
                  }`}
                >
                  {feature.title}
                </h3>
                <p
                  className={`mt-3 text-pretty leading-relaxed ${
                    feature.big
                      ? "text-ink-muted lg:text-base"
                      : "text-sm text-muted-foreground"
                  }`}
                >
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
