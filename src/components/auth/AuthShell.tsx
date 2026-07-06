import Link from "next/link";
import { EmployerAuthPanel } from "@/components/auth/EmployerAuthPanel";
import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";

export function AuthShell({
  children,
  title,
  description,
  audience = "candidate",
}: {
  children: React.ReactNode;
  title: string;
  description: string;
  audience?: "employer" | "candidate";
}) {
  return (
    <div className="min-h-screen bg-background lg:grid lg:min-h-screen lg:grid-cols-2">
      <div
        className={`noise relative hidden h-dvh max-h-dvh overflow-y-auto bg-ink px-10 py-8 text-ink-foreground lg:flex ${
          audience === "employer" ? "lg:w-full" : "lg:items-center"
        }`}
      >
        <Link
          href="/"
          className="absolute left-10 top-8 z-10 inline-flex items-center"
          aria-label="Go to PrimeScale home"
        >
          <PrimeScaleLogo variant="light" className="text-white" />
        </Link>
        {audience === "employer" ? (
          <EmployerAuthPanel title={title} description={description} />
        ) : (
          <div className="relative mx-auto flex h-full w-full max-w-xl flex-col justify-center gap-16 pt-20">
            <div className="pointer-events-none absolute -left-20 top-0 h-80 w-80 rounded-full bg-primary/20 blur-[120px]" />
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
        )}
      </div>

      <div className="flex h-dvh max-h-dvh min-h-0 w-full flex-col overflow-hidden px-5 sm:px-8">
        <div className="pt-5 sm:pt-6">
          <Link
            href="/"
            className="inline-flex items-center lg:hidden"
            aria-label="Go to PrimeScale home"
          >
            <PrimeScaleLogo variant="dark" />
          </Link>
        </div>
        <div className="flex min-h-0 w-full flex-1 flex-col justify-center pt-10 pb-14 sm:pt-12 sm:pb-16 lg:pt-16">
          {children}
        </div>
      </div>
    </div>
  );
}
