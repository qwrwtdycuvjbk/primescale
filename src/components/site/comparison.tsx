import { Reveal, Stagger, StaggerItem } from "./reveal";
import { X } from "lucide-react";

const typicalHiring = [
  "Hundreds of applicants to sort through",
  "Weeks spent screening resumes",
  "You coordinate payroll and compliance yourself",
];

const primeScale = [
  "3–5 interview-ready matches in 24 hours",
  "Recruiter-reviewed before you see anyone",
  "People Prime handles payroll, compliance, onboarding",
];

export function Comparison() {
  return (
    <section id="why-us" className="border-y border-border bg-secondary py-20 sm:py-28">
      <div className="mx-auto w-full max-w-screen-2xl px-8 sm:px-10 lg:px-12">
        <Reveal>
          <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">
            <span className="text-primary">[03]</span>
            <span>The difference</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className="display-headline mt-6 max-w-3xl text-balance text-4xl sm:text-6xl">
            Post a role.{" "}
            <span className="italic text-primary">Get matches, not a pile of resumes.</span>
          </h2>
          <p className="mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground">
            Most hiring still starts with a job post and ends with weeks of screening.
            PrimeScale flips that. Post free, get a curated shortlist in 24 hours, and
            hire with People Prime handling vetting, payroll, compliance, and onboarding.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-6 lg:grid-cols-2">
          <Reveal delay={0.08}>
            <div className="h-full rounded-3xl border border-border bg-card p-8 sm:p-10">
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
                Typical hiring
              </p>
              <h3 className="display-headline mt-4 text-4xl text-muted-foreground">
                Post and screen
              </h3>
              <Stagger className="mt-8">
                {typicalHiring.map((item) => (
                  <StaggerItem key={item}>
                    <div className="flex items-start gap-3 border-t border-border py-5 text-muted-foreground">
                      <span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted">
                        <X className="h-3 w-3" />
                      </span>
                      <p className="text-pretty text-lg font-medium leading-relaxed">
                        {item}
                      </p>
                    </div>
                  </StaggerItem>
                ))}
              </Stagger>
            </div>
          </Reveal>

          <Reveal delay={0.16}>
            <div className="noise h-full rounded-3xl border border-primary/30 bg-ink p-8 text-ink-foreground sm:p-10">
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">
                PrimeScale
              </p>
              <h3 className="display-headline mt-4 text-4xl">
                Post and get matched
              </h3>
              <Stagger className="mt-8">
                {primeScale.map((item) => (
                  <StaggerItem key={item}>
                    <div className="flex items-start gap-3 border-t border-white/10 py-5">
                      <span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary">
                        <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                      </span>
                      <p className="text-pretty text-lg font-medium leading-relaxed text-ink-muted">
                        {item}
                      </p>
                    </div>
                  </StaggerItem>
                ))}
              </Stagger>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
