import { Building2, FilePen, UserCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const steps: {
  title: string;
  description: string;
  icon: LucideIcon;
}[] = [
  {
    title: "Build company profile",
    description: "Set up your brand, team size, and hiring needs in minutes.",
    icon: Building2,
  },
  {
    title: "Post a job",
    description: "Write a role description or let AI draft one for you.",
    icon: FilePen,
  },
  {
    title: "Get a shortlist of candidates in 24 hours",
    description: "Our AI matches pre-vetted talent to your requirements instantly.",
    icon: UserCheck,
  },
];

export function EmployerAuthPanel({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="relative flex h-full w-full flex-col justify-center py-6">
      <div className="pointer-events-none absolute -left-20 top-0 h-80 w-80 rounded-full bg-primary/20 blur-[120px]" />

      <div className="relative max-w-lg">
        <h1 className="display-headline text-4xl leading-tight sm:text-5xl">{title}</h1>
        <p className="mt-4 text-base leading-relaxed text-ink-muted">{description}</p>

        <ol className="relative mt-10">
          {steps.map((step, index) => {
            const Icon = step.icon;
            const isLast = index === steps.length - 1;

            return (
              <li key={step.title} className="relative flex gap-4">
                <div className="flex flex-col items-center">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/15 bg-ink">
                    <Icon className="h-[18px] w-[18px] text-primary" strokeWidth={1.75} />
                  </div>
                  {!isLast && <span className="my-1 w-px flex-1 bg-white/15" aria-hidden />}
                </div>

                <div className={isLast ? "pb-0 pt-1.5" : "pb-8 pt-1.5"}>
                  <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-foreground">
                    {step.title}
                  </h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
                    {step.description}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
