import { Reveal, Stagger, StaggerItem } from "./reveal";
import { X } from "lucide-react";
import {
  appContainerClass,
  siteBodyClass,
  siteEyebrowClass,
  siteHeadlineClass,
  siteSectionClass,
} from "@/components/site/layout";

const typicalHiring = [
  "Hundreds of applicants to sort",
  "Weeks screening resumes",
  "You handle payroll and compliance",
];

const primeScale = [
  "3–5 interview-ready matches in 24h",
  "Recruiter-reviewed before you see anyone",
  "People Prime handles payroll and onboarding",
];

export function Comparison() {
  return (
    <section
      id="the-difference"
      className={`border-y border-border bg-secondary ${siteSectionClass}`}
    >
      <div className={appContainerClass}>
        <Reveal>
          <div className={siteEyebrowClass}>
            <span className="text-primary">[04]</span>
            <span>The difference</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className={siteHeadlineClass}>
            Matches,{" "}
            <span className="italic text-primary">not resume piles.</span>
          </h2>
          <p className={siteBodyClass}>
            Post free. Get a recruiter-reviewed shortlist in 24 hours. People
            Prime handles vetting, payroll, and onboarding.
          </p>
        </Reveal>

        <div className="mt-10 grid gap-5 lg:grid-cols-2">
          <Reveal delay={0.08}>
            <div className="h-full rounded-2xl border border-border bg-card p-6 sm:p-8">
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
                Typical hiring
              </p>
              <h3 className="display-headline mt-3 text-3xl text-muted-foreground">
                Post and screen
              </h3>
              <Stagger className="mt-6">
                {typicalHiring.map((item) => (
                  <StaggerItem key={item}>
                    <div className="flex items-start gap-3 border-t border-border py-4 text-muted-foreground">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted">
                        <X className="h-3 w-3" />
                      </span>
                      <p className="text-pretty font-medium leading-relaxed">
                        {item}
                      </p>
                    </div>
                  </StaggerItem>
                ))}
              </Stagger>
            </div>
          </Reveal>

          <Reveal delay={0.16}>
            <div className="noise h-full rounded-2xl border border-primary/30 bg-ink p-6 text-ink-foreground sm:p-8">
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">
                PrimeScale
              </p>
              <h3 className="display-headline mt-3 text-3xl">
                Post and match
              </h3>
              <Stagger className="mt-6">
                {primeScale.map((item) => (
                  <StaggerItem key={item}>
                    <div className="flex items-start gap-3 border-t border-white/10 py-4">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary">
                        <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                      </span>
                      <p className="text-pretty font-medium leading-relaxed text-ink-muted">
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
