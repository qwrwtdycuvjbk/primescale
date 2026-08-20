import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { SiteHeader } from "@/components/site/site-header";
import { SiteFooter } from "@/components/site/site-footer";
import {
  appContainerClass,
  siteBodyClass,
  siteEyebrowClass,
  siteHeadlineClass,
  siteSectionClass,
} from "@/components/site/layout";
import { ROLE_CATEGORIES } from "@/lib/constants";
import {
  MATCHING_SEATS,
  MATCHING_STATUS_LABEL,
  candidateQueueSignupHref,
  type MatchingSeatStatus,
} from "@/lib/matching-seats";

export const metadata: Metadata = {
  title: "Matching this week | People Remotely",
  description:
    "Remote tech seats People Remotely is actively shortlisting. Join a matching queue or post your role free.",
};

const statusTone: Record<MatchingSeatStatus, string> = {
  collecting: "border-border bg-muted text-muted-foreground",
  shortlisting: "border-primary/40 bg-primary/15 text-foreground",
  trial: "border-primary bg-primary text-primary-foreground",
};

export default function MatchingThisWeekPage() {
  return (
    <main className="bg-background">
      <SiteHeader />

      <section className="noise relative overflow-hidden bg-ink pt-28 pb-16 text-ink-foreground sm:pt-32">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              "radial-gradient(ellipse 80% 60% at 12% 20%, rgba(213, 236, 100, 0.18) 0%, transparent 55%)",
          }}
          aria-hidden
        />
        <div className={`relative ${appContainerClass}`}>
          <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-ink-muted">
            <span className="text-primary">[Matching]</span>
            <span>This week</span>
            <span className="h-px flex-1 bg-white/15" />
          </div>
          <h1 className="display-headline mt-5 max-w-3xl text-balance text-4xl sm:text-5xl lg:text-6xl">
            Roles we&apos;re{" "}
            <span className="italic text-primary">actively matching.</span>
          </h1>
          <p className="mt-5 max-w-xl text-pretty text-base leading-relaxed text-ink-muted sm:text-lg">
            Not a scraped job board. These are seats we&apos;re shortlisting
            right now. Candidates join a queue by category. Companies post free
            and get a small vetted shortlist.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/auth/employer/signup"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-7 py-3.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
            >
              Post yours free
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/auth/candidate/signup"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 px-7 py-3.5 text-sm font-semibold transition-colors hover:bg-white/5"
            >
              Join the matching queue
              <ArrowUpRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <section className={siteSectionClass}>
        <div className={appContainerClass}>
          <div className={siteEyebrowClass}>
            <span className="text-primary">[01]</span>
            <span>Active seats</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className={siteHeadlineClass}>
            Shortlist theater,{" "}
            <span className="italic text-primary">not empty cards.</span>
          </h2>
          <p className={siteBodyClass}>
            Status updates as we collect profiles, shortlist, or run a 2-day
            trial.
          </p>

          <ul className="mt-10 divide-y divide-border border-y border-border">
            {MATCHING_SEATS.map((seat, index) => (
              <li
                key={seat.id}
                className="grid gap-4 py-8 sm:grid-cols-[auto_1fr_auto] sm:items-start sm:gap-8"
              >
                <span className="font-mono text-xs text-muted-foreground">
                  0{index + 1}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="display-headline text-2xl sm:text-3xl">
                      {seat.title}
                    </h3>
                    <span
                      className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] ${statusTone[seat.status]}`}
                    >
                      {MATCHING_STATUS_LABEL[seat.status]}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {seat.stack} · {seat.remoteScope}
                  </p>
                  <p className="mt-3 max-w-2xl text-pretty text-sm leading-relaxed text-foreground/80">
                    Screening for: {seat.screeningFor}
                  </p>
                </div>
                <Link
                  href={candidateQueueSignupHref(seat.category)}
                  className="inline-flex shrink-0 items-center justify-center gap-2 self-start rounded-full border border-border px-5 py-2.5 text-sm font-semibold transition-colors hover:bg-muted"
                >
                  Join {seat.category} queue
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className={`border-t border-border bg-secondary ${siteSectionClass}`}>
        <div className={appContainerClass}>
          <div className={siteEyebrowClass}>
            <span className="text-primary">[02]</span>
            <span>Matching queues</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <h2 className={siteHeadlineClass}>
            Pick a category.{" "}
            <span className="italic text-primary">Get in line.</span>
          </h2>
          <p className={siteBodyClass}>
            One profile. Ongoing matches for remote tech seats in your lane.
          </p>
          <div className="mt-8 flex flex-wrap gap-2">
            {ROLE_CATEGORIES.map((category) => (
              <Link
                key={category}
                href={candidateQueueSignupHref(category)}
                className="rounded-full border border-border bg-card px-4 py-2 text-sm font-medium transition-colors hover:border-foreground/30 hover:bg-background"
              >
                {category}
              </Link>
            ))}
          </div>
          <div className="mt-10 flex flex-col gap-3 border-t border-border pt-8 sm:flex-row sm:items-center sm:justify-between">
            <p className="max-w-md text-sm text-muted-foreground">
              Hiring? Post free. Get a small vetted shortlist in 24 hours, plus
              an optional 2-day trial.
            </p>
            <Link
              href="/auth/employer/signup"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-semibold text-background transition-transform hover:-translate-y-0.5"
            >
              Post a role free
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
