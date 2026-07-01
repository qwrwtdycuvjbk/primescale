import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";
import { Check } from "lucide-react";

const benefits = [
  "Post US remote tech roles — free",
  "AI-matched candidates in 24 hours",
  "Backed by 14+ years of staffing expertise",
];

const stats = [
  { stat: "50k+", label: "Deployments" },
  { stat: "24h", label: "To matches" },
  { stat: "14+", label: "Years" },
];

export function EmployerAuthPanel({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="relative flex h-full w-full flex-col justify-between py-8">
      <div className="pointer-events-none absolute -left-20 top-0 h-80 w-80 rounded-full bg-primary/20 blur-[120px]" />

      <div className="relative">
        <PrimeScaleLogo className="relative h-10" />

        <h1 className="display-headline mt-10 text-4xl sm:text-5xl">{title}</h1>
        <p className="mt-4 max-w-sm text-base leading-relaxed text-ink-muted">
          {description}
        </p>

        <ul className="mt-8 space-y-3">
          {benefits.map((benefit) => (
            <li key={benefit} className="flex items-center gap-3">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/20">
                <Check className="h-3 w-3 text-primary" />
              </span>
              <span className="text-sm text-ink-foreground">{benefit}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="relative border-t border-white/10 pt-6">
        <div className="flex gap-6">
          {stats.map((item) => (
            <div key={item.label}>
              <p className="text-xl font-bold text-primary">{item.stat}</p>
              <p className="text-xs text-ink-muted">{item.label}</p>
            </div>
          ))}
        </div>

        <p className="mt-4 text-xs text-ink-muted">
          By People Prime Worldwide
        </p>
      </div>
    </div>
  );
}
