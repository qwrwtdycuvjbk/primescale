import Link from "next/link";
import { Reveal } from "./reveal";
import { ArrowRight, Briefcase, UserRound } from "lucide-react";
import {
  appContainerClass,
  siteBodyClass,
  siteEyebrowClass,
  siteHeadlineClass,
  siteSectionClass,
} from "@/components/site/layout";

const cards = [
  {
    icon: Briefcase,
    kicker: "For employers",
    title: "I'm hiring",
    body: "Post a US remote tech role. Get recruiter-reviewed matches in your dashboard.",
    points: [
      "AI-assisted JD parsing",
      "Skill and seniority matching",
      "One shortlist dashboard",
    ],
    cta: "Post a role",
    href: "/auth/employer/signup",
    accent: true,
  },
  {
    icon: UserRound,
    kicker: "For candidates",
    title: "I'm a candidate",
    body: "One profile. Ongoing matches to US remote tech roles that fit.",
    points: [
      "One profile, ongoing matches",
      "US remote tech only",
      "Mark roles you want",
    ],
    cta: "Get matched",
    href: "/auth/candidate/signup",
    accent: false,
  },
];

export function GetStarted() {
  return (
    <section id="get-started" className={`bg-background ${siteSectionClass}`}>
      <div className={appContainerClass}>
        <Reveal className="max-w-2xl">
          <div className={siteEyebrowClass}>
            <span className="text-primary">[06]</span>
            <span>Get started</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className={siteHeadlineClass}>
            Pick a path. <span className="italic text-primary">Go.</span>
          </h2>
          <p className={siteBodyClass}>Free to start. US remote tech only.</p>
        </Reveal>

        <div className="mt-8 grid gap-4 lg:grid-cols-2">
          {cards.map((card, i) => (
            <Reveal key={card.title} delay={i * 0.12}>
              <div
                className={`group relative flex h-full flex-col overflow-hidden rounded-2xl border p-6 transition-transform hover:-translate-y-1 sm:p-8 ${
                  card.accent
                    ? "noise border-transparent bg-ink text-ink-foreground"
                    : "border-border bg-card"
                }`}
              >
                <div className="relative flex items-center justify-between">
                  <span
                    className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                      card.accent
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground"
                    }`}
                  >
                    <card.icon className="h-5 w-5" />
                  </span>
                  <span
                    className={`font-mono text-xs uppercase tracking-[0.2em] ${
                      card.accent ? "text-ink-muted" : "text-muted-foreground"
                    }`}
                  >
                    {card.kicker}
                  </span>
                </div>

                <h3 className="display-headline relative mt-6 text-3xl">
                  {card.title}
                </h3>
                <p
                  className={`relative mt-2 text-sm leading-relaxed ${
                    card.accent ? "text-ink-muted" : "text-muted-foreground"
                  }`}
                >
                  {card.body}
                </p>

                <ul className="relative mt-5 flex flex-col">
                  {card.points.map((point) => (
                    <li
                      key={point}
                      className={`flex items-center gap-3 border-t py-2.5 text-sm ${
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
                  className={`relative mt-6 inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition-all group-hover:gap-3 ${
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
