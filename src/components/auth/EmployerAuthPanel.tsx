import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";

const green = "#9CB86A";

function CandidateShortlistIcon() {
  return (
    <svg width="88" height="52" viewBox="0 0 88 52" fill="none" aria-hidden>
      <circle cx="22" cy="30" r="14" fill={green} fillOpacity="0.35" stroke={green} strokeWidth="1.5" />
      <path
        d="M22 17.5c-4.2 0-7.5 3.2-7.5 7.2 0 2.4.9 4.6 2.4 6.2.8.9 1.2 2.2 1.2 3.5v2.1c0 .8.7 1.5 1.5 1.5h5.2c.8 0 1.5-.7 1.5-1.5v-2.1c0-1.3.4-2.6 1.2-3.5 1.5-1.6 2.4-3.8 2.4-6.2 0-4-3.3-7.2-7.5-7.2Z"
        fill="#FFF"
      />
      <ellipse cx="22" cy="36.5" rx="7" ry="3.5" fill={green} />
      <circle cx="44" cy="26" r="18" fill={green} stroke={green} strokeWidth="2" />
      <circle cx="44" cy="21" r="7" fill="#FFF" />
      <path d="M36.5 29.5c2.2 3.8 13.8 3.8 16 0v4.5h-16v-4.5Z" fill="#FFF" />
      <ellipse cx="44" cy="36" rx="10" ry="5" fill={green} />
      <circle cx="66" cy="30" r="14" fill={green} fillOpacity="0.35" stroke={green} strokeWidth="1.5" />
      <circle cx="66" cy="25" r="5" fill="#FFF" />
      <path d="M61.5 28.5c0-2.2 9-2.2 9 0v3.5h-9v-3.5Z" fill="#FFF" />
      <ellipse cx="66" cy="36" rx="7" ry="4" fill={green} />
    </svg>
  );
}

const stepsData = [
  {
    number: "1",
    title: "First, build your company profile.",
    description: "Highlight your company's values and culture to attract the right fit.",
    icon: (
      <div className="w-28 rounded-lg border border-white/10 bg-white/[0.04] p-2.5 shadow-lg">
        <div className="mb-2 flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-white/25" />
          <span className="h-1.5 w-1.5 rounded-full bg-white/25" />
          <span className="h-1.5 w-1.5 rounded-full bg-white/25" />
        </div>
        <div className="flex gap-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-white/15">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
              <circle cx="7" cy="5" r="2.5" stroke={green} strokeWidth="1.2" />
              <path d="M2.5 12c0-2.5 9-2.5 9 0" stroke={green} strokeWidth="1.2" strokeLinecap="round" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="text-[7px] font-medium leading-tight text-ink-foreground">Company Profile</p>
            <div className="mt-1.5 space-y-1">
              <div className="h-1 w-full rounded bg-white/15" />
              <div className="h-1 w-4/5 rounded bg-white/10" />
              <div className="h-1 w-3/5 rounded bg-white/10" />
            </div>
          </div>
        </div>
      </div>
    ),
  },
  {
    number: "2",
    title: "Then, post your open tech role.",
    description: "Input role details and requirements in under 10 minutes.",
    icon: (
      <div className="relative w-28">
        <div className="rounded-lg border border-white/10 bg-white/[0.04] p-2.5 shadow-lg">
          <p className="text-[7px] font-medium text-ink-foreground">Job description</p>
          <div className="mt-2 space-y-1.5">
            <div className="h-1 w-full rounded bg-white/15" />
            <div className="h-1 w-11/12 rounded bg-white/10" />
            <div className="h-1 w-4/5 rounded bg-white/10" />
            <div className="h-1 w-full rounded bg-white/10" />
          </div>
        </div>
        <span className="absolute -bottom-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground shadow-md">
          +
        </span>
      </div>
    ),
  },
  {
    number: "3",
    title: "Third, get a shortlist of hand-picked candidates in under 24 hours.",
    description: "Receive pre-vetted, AI-matched applicants directly in your dashboard.",
    icon: <CandidateShortlistIcon />,
  },
];

const stats = [
  { stat: "50k+", label: "Deployments" },
  { stat: "24h", label: "To matches" },
  { stat: "14+", label: "Years experience" },
];

export function EmployerAuthPanel({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="relative flex h-full w-full flex-col justify-between py-6">
      <div className="pointer-events-none absolute -left-20 top-0 h-80 w-80 rounded-full bg-primary/20 blur-[120px]" />

      <div className="relative">
        <PrimeScaleLogo className="h-12 w-auto" />

        <h1 className="display-headline mt-8 text-4xl leading-tight sm:text-5xl">{title}</h1>
        <p className="mt-4 max-w-md text-base leading-relaxed text-ink-muted">
          {description}
        </p>

        <ol className="mt-8 flex flex-col gap-5">
          {stepsData.map((step) => (
            <li key={step.number} className="flex items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                  {step.number}
                </span>
                <div>
                  <h3 className="text-base font-semibold leading-snug text-ink-foreground">
                    {step.title}
                  </h3>
                  <p className="mt-0.5 text-sm leading-relaxed text-ink-muted">
                    {step.description}
                  </p>
                </div>
              </div>
              <div className="hidden shrink-0 sm:block">{step.icon}</div>
            </li>
          ))}
        </ol>
      </div>

      <div className="relative border-t border-white/10 pt-6">
        <div className="grid grid-cols-3 gap-4">
          {stats.map((item) => (
            <div key={item.label}>
              <p className="display-headline text-3xl text-primary">{item.stat}</p>
              <p className="mt-1 text-xs text-ink-muted">{item.label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}