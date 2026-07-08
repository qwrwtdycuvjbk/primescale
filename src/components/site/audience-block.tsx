import Link from "next/link";
import { Reveal, Stagger, StaggerItem } from "./reveal";
import { ArrowRight } from "lucide-react";

type AudienceBlockProps = {
  id: string;
  index: string;
  variant: "dark" | "light";
  eyebrow: string;
  title: string;
  intro: string;
  bullets: string[];
  ctaLabel: string;
  ctaHref: string;
  reverse?: boolean;
};

export function AudienceBlock({
  id,
  index,
  variant,
  eyebrow,
  title,
  intro,
  bullets,
  ctaLabel,
  ctaHref,
  reverse,
}: AudienceBlockProps) {
  const dark = variant === "dark";

  return (
    <section
      id={id}
      className={
        dark
          ? "noise relative overflow-hidden bg-ink text-ink-foreground"
          : "relative overflow-hidden bg-secondary text-foreground"
      }
    >
      <span
        className={`display-headline pointer-events-none absolute -top-10 select-none text-[16rem] leading-none sm:text-[22rem] ${
          reverse ? "right-[-2rem]" : "left-[-2rem]"
        } ${dark ? "text-white/[0.04]" : "text-foreground/[0.04]"}`}
        aria-hidden
      >
        {index}
      </span>

      <div className="relative mx-auto grid w-full max-w-screen-2xl items-center gap-12 px-8 py-20 sm:px-10 lg:grid-cols-2 lg:gap-16 lg:px-12 lg:py-28">
        <Reveal className={reverse ? "lg:order-2" : ""}>
          <div
            className={`flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] ${
              dark ? "text-ink-muted" : "text-muted-foreground"
            }`}
          >
            <span className="text-primary">[{index}]</span>
            <span>{eyebrow}</span>
          </div>
          <h2 className="display-headline mt-6 text-balance text-4xl sm:text-6xl">
            {title}
          </h2>
          <p
            className={`mt-6 max-w-md text-pretty text-lg leading-relaxed ${
              dark ? "text-ink-muted" : "text-muted-foreground"
            }`}
          >
            {intro}
          </p>
          <Link
            href={ctaHref}
            className="group mt-8 inline-flex items-center gap-2 rounded-full bg-primary px-7 py-4 text-base font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            {ctaLabel}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Link>
        </Reveal>

        <Stagger className={reverse ? "lg:order-1" : ""}>
          {bullets.map((bullet, i) => (
            <StaggerItem key={bullet}>
              <div
                className={`group flex items-baseline gap-5 border-t py-5 transition-colors last:border-b ${
                  dark
                    ? "border-white/10 hover:bg-white/[0.04]"
                    : "border-border hover:bg-background/60"
                }`}
              >
                <span className="display-headline shrink-0 text-2xl text-primary">
                  0{i + 1}
                </span>
                <p className="text-pretty text-lg font-medium leading-relaxed">
                  {bullet}
                </p>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}
