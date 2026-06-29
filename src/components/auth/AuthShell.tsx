import Link from "next/link";
import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";

export function AuthShell({
  children,
  title,
  description,
}: {
  children: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="min-h-screen bg-background lg:grid lg:grid-cols-2">
      <div className="noise relative hidden flex-col justify-between overflow-hidden bg-ink p-10 text-ink-foreground lg:flex">
        <div className="pointer-events-none absolute -left-20 top-0 h-80 w-80 rounded-full bg-primary/20 blur-[120px]" />
        <Link href="/" className="relative">
          <PrimeScaleLogo />
        </Link>

        <div className="relative">
          <h1 className="display-headline text-5xl">{title}</h1>
          <p className="mt-6 max-w-md text-lg leading-relaxed text-ink-muted">
            {description}
          </p>
        </div>

        <div className="relative grid grid-cols-3 gap-4 border-t border-white/10 pt-8">
          {[
            { stat: "14+", label: "Years experience" },
            { stat: "50k+", label: "Deployments" },
            { stat: "24h", label: "To matches" },
          ].map((item) => (
            <div key={item.label}>
              <p className="display-headline text-3xl text-primary">{item.stat}</p>
              <p className="mt-1 text-xs text-ink-muted">{item.label}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex min-h-screen flex-col px-6 py-10 sm:px-10">
        <div className="mb-10 lg:hidden">
          <Link href="/">
            <PrimeScaleLogo variant="dark" />
          </Link>
        </div>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center">
          {children}
        </div>
      </div>
    </div>
  );
}
