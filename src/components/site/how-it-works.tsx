import { Reveal, Stagger, StaggerItem } from "./reveal";
import { Briefcase, UserRound } from "lucide-react";
import {
  appContainerClass,
  siteEyebrowClass,
  siteHeadlineClass,
  siteSectionClass,
} from "@/components/site/layout";

const candidateSteps = [
  {
    title: "Create your profile",
    body: "Skills, experience, and work eligibility. One profile for remote tech.",
  },
  {
    title: "Get matched to live seats",
    body: "We match you to roles we’re actively filling, not a dead job wall.",
  },
  {
    title: "Mark interest and move forward",
    body: "Say yes to fits. Mutual interest leads to intro with People Prime support.",
  },
];

const employerSteps = [
  {
    title: "Post your role free",
    body: "Upload your JD. AI pulls out title, stack, and seniority.",
  },
  {
    title: "Get a small shortlist",
    body: "3 to 5 vetted matches in 24 hours. No resume pile.",
  },
  {
    title: "Try before you hire",
    body: "Optional 2-day trial. People Prime helps you close and onboard.",
  },
];

function Track({
  icon,
  label,
  tag,
  accent,
  steps,
}: {
  icon: React.ReactNode;
  label: string;
  tag: string;
  accent: boolean;
  steps: { title: string; body: string }[];
}) {
  return (
    <div>
      <div className="flex items-center gap-3">
        <span
          className={`flex h-9 w-9 items-center justify-center rounded-lg ${
            accent
              ? "bg-primary text-primary-foreground"
              : "bg-foreground text-background"
          }`}
        >
          {icon}
        </span>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
            {tag}
          </p>
          <h3 className="display-headline text-xl">{label}</h3>
        </div>
      </div>

      <Stagger className="mt-6">
        {steps.map((step, i) => (
          <StaggerItem key={step.title}>
            <div className="group flex gap-4 border-t border-border py-4 transition-colors last:border-b hover:bg-muted/40">
              <span
                className={`display-headline shrink-0 text-2xl ${
                  accent ? "text-primary" : "text-muted-foreground"
                }`}
              >
                0{i + 1}
              </span>
              <div>
                <p className="font-semibold tracking-tight">{step.title}</p>
                <p className="mt-0.5 text-pretty text-sm leading-relaxed text-muted-foreground">
                  {step.body}
                </p>
              </div>
            </div>
          </StaggerItem>
        ))}
      </Stagger>
    </div>
  );
}

export function HowItWorks() {
  return (
    <section id="how-it-works" className={`bg-background ${siteSectionClass}`}>
      <div className={appContainerClass}>
        <Reveal>
          <div className={siteEyebrowClass}>
            <span className="text-primary">[02]</span>
            <span>How it works</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className={siteHeadlineClass}>
            Two paths. One <span className="italic text-primary">flow.</span>
          </h2>
        </Reveal>

        <div className="relative mt-10 grid gap-10 lg:grid-cols-2 lg:gap-12">
          <div className="pointer-events-none absolute inset-y-0 left-1/2 hidden -translate-x-1/2 lg:block">
            <div className="h-full w-px bg-border" />
            <span className="display-headline absolute left-1/2 top-1/2 flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-background text-lg italic text-primary">
              &amp;
            </span>
          </div>

          <Reveal>
            <Track
              icon={<Briefcase className="h-4 w-4" />}
              label="For employers"
              tag="Hiring"
              accent
              steps={employerSteps}
            />
          </Reveal>
          <Reveal delay={0.12}>
            <Track
              icon={<UserRound className="h-4 w-4" />}
              label="For candidates"
              tag="Talent"
              accent={false}
              steps={candidateSteps}
            />
          </Reveal>
        </div>
      </div>
    </section>
  );
}
