import { Reveal, Stagger, StaggerItem } from "./reveal";
import { Briefcase, UserRound } from "lucide-react";
import { appContainerClass } from "@/components/site/layout";

const employerSteps = [
  {
    title: "Post your role",
    body: "Paste your JD or fill in details. AI helps structure the role for better matching.",
  },
  {
    title: "Get matched candidates",
    body: "PrimeScale scores candidates on skills, seniority, and US work requirements. No inbox flood.",
  },
  {
    title: "Shortlist and hire",
    body: "Review matches, shortlist the best fits, and move forward with People Prime support.",
  },
];

const candidateSteps = [
  {
    title: "Build your profile",
    body: "Add your skills, experience, and US work authorization. One profile, no endless applications.",
  },
  {
    title: "Get matched to roles",
    body: "Our engine surfaces US remote tech roles that fit your profile and preferences.",
  },
  {
    title: "Express interest",
    body: "Review matches, mark roles you want, and connect when there is mutual fit.",
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
          className={`flex h-10 w-10 items-center justify-center rounded-xl ${
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
          <h3 className="display-headline text-2xl">{label}</h3>
        </div>
      </div>

      <Stagger className="mt-8">
        {steps.map((step, i) => (
          <StaggerItem key={step.title}>
            <div className="group flex gap-5 border-t border-border py-6 transition-colors last:border-b hover:bg-muted/40">
              <span
                className={`display-headline shrink-0 text-3xl ${
                  accent ? "text-primary" : "text-muted-foreground"
                }`}
              >
                0{i + 1}
              </span>
              <div>
                <p className="text-lg font-semibold tracking-tight">
                  {step.title}
                </p>
                <p className="mt-1 text-pretty leading-relaxed text-muted-foreground">
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
    <section id="how-it-works" className="bg-background py-20 sm:py-28">
      <div className={appContainerClass}>
        <Reveal>
          <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">
            <span className="text-primary">[02]</span>
            <span>How it works</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className="display-headline mt-6 max-w-3xl text-balance text-4xl sm:text-6xl">
            Two paths. One refreshingly{" "}
            <span className="italic text-primary">simple</span> flow.
          </h2>
        </Reveal>

        <div className="relative mt-14 grid gap-12 lg:grid-cols-2 lg:gap-16">
          <div className="pointer-events-none absolute inset-y-0 left-1/2 hidden -translate-x-1/2 lg:block">
            <div className="h-full w-px bg-border" />
            <span className="display-headline absolute left-1/2 top-1/2 flex h-12 w-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-background text-xl italic text-primary">
              &amp;
            </span>
          </div>

          <Reveal>
            <Track
              icon={<Briefcase className="h-5 w-5" />}
              label="For employers"
              tag="The hiring side"
              accent
              steps={employerSteps}
            />
          </Reveal>
          <Reveal delay={0.12}>
            <Track
              icon={<UserRound className="h-5 w-5" />}
              label="For candidates"
              tag="The talent side"
              accent={false}
              steps={candidateSteps}
            />
          </Reveal>
        </div>
      </div>
    </section>
  );
}
