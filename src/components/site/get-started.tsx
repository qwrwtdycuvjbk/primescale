import Link from "next/link";
import { Reveal } from "./reveal";
import { ArrowRight, Briefcase, UserRound } from "lucide-react";
import { appContainerClass } from "@/components/site/layout";

const cards = [
  {
    icon: Briefcase,
    kicker: "For employers",
    title: "I'm hiring",
    body: "Post a US remote tech role free and get AI-matched candidates in your dashboard.",
    points: [
      "AI-assisted JD parsing",
      "Skill and seniority matching",
      "Shortlist from one dashboard",
    ],
    cta: "Post a role",
    href: "/auth/employer/signup",
    accent: true,
  },
  {
    icon: UserRound,
    kicker: "For candidates",
    title: "I'm a candidate",
    body: "Build one profile and get matched to US remote tech roles that fit.",
    points: [
      "One profile, ongoing matches",
      "US tech roles only",
      "Mark roles you're interested in",
    ],
    cta: "Get matched",
    href: "/auth/candidate/signup",
    accent: false,
  },
];

export function GetStarted() {
  return (
    <section id="get-started" className="bg-background py-20 sm:py-28">
      <div className={appContainerClass}>
        <Reveal className="max-w-3xl">
          <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">
            <span className="text-primary">[06]</span>
            <span>Get started</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className="display-headline mt-6 text-balance text-4xl sm:text-6xl">
            Pick your path and <span className="italic text-primary">go.</span>
          </h2>
          <p className="mt-4 text-pretty text-lg leading-relaxed text-muted-foreground">
            Free to start on both sides. US remote tech roles only.
          </p>
        </Reveal>

        <div className="mt-12 grid gap-5 lg:grid-cols-2">
          {cards.map((card, i) => (
            <Reveal key={card.title} delay={i * 0.12}>
              <div
                className={`group relative flex h-full flex-col overflow-hidden rounded-3xl border p-8 transition-transform hover:-translate-y-1 sm:p-10 ${
                  card.accent
                    ? "noise border-transparent bg-ink text-ink-foreground"
                    : "border-border bg-card"
                }`}
              >
                <div className="relative flex items-center justify-between">
                  <span
                    className={`flex h-12 w-12 items-center justify-center rounded-xl ${
                      card.accent
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground"
                    }`}
                  >
                    <card.icon className="h-6 w-6" />
                  </span>
                  <span
                    className={`font-mono text-xs uppercase tracking-[0.2em] ${
                      card.accent ? "text-ink-muted" : "text-muted-foreground"
                    }`}
                  >
                    {card.kicker}
                  </span>
                </div>

                <h3 className="display-headline relative mt-8 text-4xl sm:text-5xl">
                  {card.title}
                </h3>
                <p
                  className={`relative mt-3 leading-relaxed ${
                    card.accent ? "text-ink-muted" : "text-muted-foreground"
                  }`}
                >
                  {card.body}
                </p>

                <ul className="relative mt-7 flex flex-col">
                  {card.points.map((point) => (
                    <li
                      key={point}
                      className={`flex items-center gap-3 border-t py-3 text-sm ${
                        card.accent ? "border-white/10" : "border-border"
                      }`}
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                      {point}
                    </li>
                  ))}
                </ul>

                <Link
                  href={card.href}
                  className={`relative mt-8 inline-flex items-center justify-center gap-2 rounded-full px-6 py-4 text-base font-semibold transition-all group-hover:gap-3 ${
                    card.accent
                      ? "bg-primary text-primary-foreground"
                      : "bg-foreground text-background"
                  }`}
                >
                  {card.cta}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
