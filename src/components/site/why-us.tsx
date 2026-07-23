import {
  Crosshair,
  FilePenLine,
  Globe2,
  Handshake,
  UserCheck,
  Zap,
} from "lucide-react";
import { Reveal, Stagger, StaggerItem } from "./reveal";
import {
  appContainerClass,
  siteBodyClass,
  siteEyebrowClass,
  siteHeadlineClass,
  siteSectionClass,
} from "./layout";

const features = [
  {
    icon: UserCheck,
    title: "Recruiter-Reviewed",
    body: "Every candidate is vetted by a real recruiter, not just AI-matched.",
  },
  {
    icon: Globe2,
    title: "Global Remote Roles",
    body: "Access talent worldwide. Work eligibility verified for every match.",
  },
  {
    icon: Handshake,
    title: "People Prime Backing",
    body: "Payroll, compliance, and onboarding handled by staffing experts.",
  },
  {
    icon: Zap,
    title: "Free to Post",
    body: "No upfront fees. Post a role and only pay when you hire.",
  },
  {
    icon: FilePenLine,
    title: "Contract or C2H",
    body: "Flexible engagement models. Contract, contract-to-hire, or direct.",
  },
  {
    icon: Crosshair,
    title: "Stack-Aligned Matching",
    body: "AI parses your JD and matches on exact skills and seniority.",
  },
];

export function WhyUs() {
  return (
    <section
      id="why-us"
      className={`noise relative overflow-hidden bg-ink text-ink-foreground ${siteSectionClass}`}
    >
      <div className={`relative z-10 ${appContainerClass}`}>
        <Reveal>
          <div className={`${siteEyebrowClass} text-ink-muted`}>
            <span className="text-primary">[03]</span>
            <span>Why us</span>
            <span className="h-px flex-1 bg-white/10" />
          </div>
          <h2 className={`${siteHeadlineClass} text-ink-foreground`}>
            Recruiter-reviewed.{" "}
            <span className="italic text-primary">Globally ready.</span>
          </h2>
          <p className={`${siteBodyClass} text-ink-muted`}>
            Free to post. People Prime handles vetting, payroll, and onboarding.
          </p>
        </Reveal>

        <Stagger className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <StaggerItem key={feature.title}>
              <div className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.04] p-6 transition-colors hover:bg-white/[0.06] sm:p-7">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/15 text-primary">
                  <feature.icon className="h-5 w-5" strokeWidth={2} />
                </span>
                <h3 className="mt-6 text-lg font-semibold tracking-tight text-ink-foreground">
                  {feature.title}
                </h3>
                <p className="mt-2 text-pretty text-sm leading-relaxed text-ink-muted">
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
