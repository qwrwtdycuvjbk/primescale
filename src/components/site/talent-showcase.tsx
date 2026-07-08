import Link from "next/link";
import { ArrowRight, BadgeCheck, Briefcase, ChevronRight, Lock } from "lucide-react";
import type { PublicTalentCard } from "@/lib/public-talent";
import { appContainerClass } from "@/components/site/layout";
import { Reveal, Stagger, StaggerItem } from "./reveal";

const employerSignupHref = "/auth/employer/signup?source=talent";

function TalentCard({ candidate }: { candidate: PublicTalentCard }) {
  const locationLine = [candidate.location, candidate.workAuthorizationLabel]
    .filter(Boolean)
    .join(" · ");

  return (
    <article className="flex h-full flex-col rounded-2xl border border-border bg-card shadow-sm transition hover:border-primary/35 hover:shadow-md">
      <div className="flex flex-1 flex-col p-7">
        <div className="flex items-start gap-4">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-primary/10 font-display text-lg font-semibold text-primary ring-2 ring-primary/15">
            {candidate.initials}
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            <p className="truncate text-base font-semibold leading-snug">{candidate.displayName}</p>
            {locationLine && (
              <p className="truncate text-sm leading-relaxed text-muted-foreground">{locationLine}</p>
            )}
            <p className="truncate text-sm leading-relaxed text-muted-foreground">{candidate.title}</p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-border pb-6 text-sm leading-relaxed">
          {candidate.salaryRange && (
            <span className="font-semibold text-foreground">{candidate.salaryRange}</span>
          )}
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
            <BadgeCheck className="h-4 w-4 text-primary" aria-hidden />
            Recruiter vetted
          </span>
          {(candidate.yearsExperience != null || candidate.experienceLevelLabel) && (
            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
              <Briefcase className="h-4 w-4" aria-hidden />
              {candidate.yearsExperience != null
                ? `${candidate.yearsExperience} yrs`
                : candidate.experienceLevelLabel}
            </span>
          )}
        </div>

        <div className="relative mt-6 min-h-[6.5rem]">
          {candidate.bioSnippet ? (
            <p className="line-clamp-4 text-sm leading-7 text-muted-foreground">
              {candidate.bioSnippet}
            </p>
          ) : (
            <p className="line-clamp-4 text-sm leading-7 text-muted-foreground">
              {candidate.title}. Skills include {candidate.skills.slice(0, 2).join(", ")}
              {candidate.hiddenSkillCount > 0 ? " and more" : ""} — full profile available
              after you post a role.
            </p>
          )}
          <div
            className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-card to-transparent"
            aria-hidden
          />
        </div>

        <div className="mt-6 flex items-center gap-2 overflow-hidden">
          <div className="flex min-w-0 flex-1 gap-2.5 overflow-x-auto pb-1">
            {candidate.skills.map((skill) => (
              <span
                key={skill}
                className="shrink-0 rounded-full border border-border bg-muted/40 px-3 py-1.5 text-xs leading-relaxed text-foreground"
              >
                {skill}
              </span>
            ))}
            {candidate.hiddenSkillCount > 0 && (
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-dashed border-border px-3 py-1.5 text-xs leading-relaxed text-muted-foreground">
                <Lock className="h-3 w-3" aria-hidden />
                +{candidate.hiddenSkillCount} skills
              </span>
            )}
          </div>
          {candidate.hiddenSkillCount > 0 && (
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          )}
        </div>

        {candidate.roleCategories.length > 0 && (
          <p className="mt-5 font-mono text-[11px] uppercase tracking-[0.16em] text-primary">
            {candidate.roleCategories.join(" · ")}
          </p>
        )}
      </div>

      <div className="border-t border-border p-6">
        <Link
          href={employerSignupHref}
          className="flex w-full items-center justify-center rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition hover:opacity-95"
        >
          See profile
        </Link>
        <p className="mt-3 text-center text-xs leading-relaxed text-muted-foreground">
          Sign in to view resume, links & contact
        </p>
      </div>
    </article>
  );
}

export function TalentShowcase({ candidates }: { candidates: PublicTalentCard[] }) {
  return (
    <section id="available-talent" className="bg-background py-20 sm:py-28">
      <div className={appContainerClass}>
        <Reveal>
          <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">
                <span className="text-primary">[04]</span>
                <span>Available talent</span>
                <span className="h-px flex-1 bg-border lg:hidden" />
              </div>
              <h2 className="display-headline mt-6 text-balance text-4xl sm:text-6xl">
                Browse vetted{" "}
                <span className="italic text-primary">global remote</span> engineers.
              </h2>
              <p className="mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground">
                {candidates.length > 0
                  ? "Preview interview-ready talent. Full profiles, resumes, and contact details unlock when you post a role."
                  : "Post a role and our recruiters will match you with interview-ready remote engineers from our network."}
              </p>
            </div>

            <Link
              href={employerSignupHref}
              className="group inline-flex shrink-0 items-center gap-2 rounded-full bg-primary px-7 py-4 text-base font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
            >
              Post a role to unlock profiles
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </Reveal>

        {candidates.length > 0 ? (
          <Stagger className="mt-14 grid gap-7 md:grid-cols-2 xl:grid-cols-3">
            {candidates.map((candidate) => (
              <StaggerItem key={candidate.id}>
                <TalentCard candidate={candidate} />
              </StaggerItem>
            ))}
          </Stagger>
        ) : (
          <Reveal delay={0.1}>
            <div className="mt-14 rounded-3xl border border-dashed border-border bg-muted/30 px-6 py-16 text-center sm:px-10">
              <p className="display-headline text-3xl sm:text-4xl">
                Talent profiles are growing.
              </p>
              <p className="mx-auto mt-4 max-w-xl text-pretty text-muted-foreground">
                Post your first role and People Prime will deliver recruiter-vetted
                matches within 24 hours — from candidates on the platform and our
                broader staffing network.
              </p>
              <Link
                href={employerSignupHref}
                className="mt-8 inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-3 text-sm font-semibold transition-colors hover:border-primary/50"
              >
                Post a role for free
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </Reveal>
        )}

        <Reveal delay={0.15}>
          <p className="mt-8 text-center text-sm text-muted-foreground">
            Public previews only — names are abbreviated, bios truncated, and contact
            details stay hidden until you sign in and match.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
