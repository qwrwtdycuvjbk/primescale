"use client";

import React from "react";
import Link from "next/link";
import {
  KeyRound,
  FileText,
  LayoutDashboard,
  Target,
  SearchCheck,
  ExternalLink,
  ClipboardList,
  ArrowRight,
  ArrowUpRight,
  Sparkles,
} from "lucide-react";
import { appContainerClass } from "@/components/site/layout";
import { Reveal, Stagger, StaggerItem } from "@/components/site/reveal";

const workflowSteps = [
  {
    step: "01",
    title: "Sign Up or Sign In",
    icon: KeyRound,
    summary: "Create an account or log in seamlessly",
    description:
      "Sign in to your existing candidate account or register in seconds using your email and password or 1-click Google authentication.",
  },
  {
    step: "02",
    title: "Complete Your Profile",
    icon: FileText,
    summary: "Add your details and upload your resume",
    description:
      "Provide your job title, experience level, and upload your resume. Keeping your profile up to date ensures your job matching is as accurate as possible.",
  },
  {
    step: "03",
    title: "Your Dashboard",
    icon: LayoutDashboard,
    summary: "All candidate features in one unified hub",
    description:
      "Access your centralized candidate dashboard to view your profile completion, review matching opportunities, track applications, and manage your account.",
  },
  {
    step: "04",
    title: "Discover Job Matches",
    icon: Target,
    summary: "Personalized match feed with relevance scores",
    description:
      "The dashboard automatically surfaces matching opportunities based on your skills, experience, and role preferences with transparent match percentages.",
  },
  {
    step: "05",
    title: "Review Job Details",
    icon: SearchCheck,
    summary: "Inspect complete requirements and compensation",
    description:
      "Open any matched position to review the in-depth job description, hiring company, location, work mode (remote/hybrid), salary (when available), and required stack.",
  },
  {
    step: "06",
    title: "Apply to the Role",
    icon: ExternalLink,
    summary: "Direct submission or external employer redirect",
    description:
      "Click the Apply action. For external roles, you are redirected directly to the employer's official careers site to submit your application securely.",
  },
  {
    step: "07",
    title: "Track Applications",
    icon: ClipboardList,
    summary: "Monitor your application pipeline",
    description:
      "Keep track of the jobs you've applied for from your dashboard application tracker, providing a clear history of your job search progress.",
  },
];

export function DashboardWorkflow() {
  return (
    <section
      id="dashboard-workflow"
      className="noise relative isolate overflow-hidden bg-ink text-ink-foreground py-20 sm:py-28"
    >
      {/* Background Decorative Glows */}
      <div className="pointer-events-none absolute inset-0 z-[1]" aria-hidden>
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 80% 60% at 50% 10%, rgba(213, 236, 100, 0.12) 0%, rgba(213, 236, 100, 0.02) 40%, transparent 70%)",
          }}
        />
        <div className="absolute right-[-10%] top-[20%] size-[24rem] rounded-full bg-primary/10 blur-[120px]" />
        <div className="absolute left-[-10%] bottom-[10%] size-[20rem] rounded-full bg-primary/5 blur-[100px]" />
      </div>

      <div className={`relative z-10 ${appContainerClass}`}>
        {/* Section Header */}
        <Reveal>
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
            <div className="max-w-2xl">
              <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em] text-ink-muted">
                <span className="text-primary font-bold">[03]</span>
                <span>Candidate Dashboard &amp; Workflow</span>
                <span className="h-px flex-1 bg-white/15" />
              </div>

              <h2 className="display-headline mt-4 text-balance text-3xl font-bold tracking-tight sm:text-5xl text-ink-foreground">
                Your Jobs. Your Dashboard.{" "}
                <span className="italic text-primary block sm:inline">
                  Your Next Opportunity.
                </span>
              </h2>

              <p className="mt-4 text-pretty text-base leading-relaxed text-ink-muted sm:text-lg">
                Manage your profile, discover relevant jobs, and keep track of your
                applications from one unified place.
              </p>
            </div>

            {/* Quick CTAs */}
            <div className="flex flex-wrap items-center gap-3 shrink-0">
              <Link
                href="/candidate"
                className="group inline-flex items-center justify-center gap-2 rounded-full bg-primary px-7 py-3.5 text-sm font-semibold text-primary-foreground shadow-[0_0_30px_-8px_rgba(213,236,100,0.5)] transition-transform hover:-translate-y-0.5"
              >
                <span>Go to Dashboard</span>
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/auth/candidate/signup"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 px-7 py-3.5 text-sm font-semibold text-ink-foreground transition-colors hover:bg-white/10"
              >
                <span>Sign Up Free</span>
                <ArrowUpRight className="h-4 w-4 text-primary" />
              </Link>
            </div>
          </div>
        </Reveal>

        {/* 7-Step Workflow Layout */}
        <Stagger className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {workflowSteps.map((step, idx) => {
            const IconComponent = step.icon;
            const isLast = idx === workflowSteps.length - 1;
            return (
              <StaggerItem
                key={step.step}
                className={isLast ? "sm:col-span-2 lg:col-span-3 xl:col-span-2" : ""}
              >
                <div className="group relative flex h-full flex-col justify-between rounded-3xl border border-white/10 bg-white/[0.04] p-6 backdrop-blur-sm transition-all duration-300 hover:border-primary/40 hover:bg-white/[0.07]">
                  <div>
                    {/* Header: Step Number & Icon */}
                    <div className="flex items-center justify-between">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                        <IconComponent className="h-5 w-5" />
                      </div>
                      <span className="font-mono text-xs font-bold uppercase tracking-widest text-primary">
                        Step {step.step}
                      </span>
                    </div>

                    <h3 className="mt-5 text-lg font-bold text-ink-foreground">
                      {step.title}
                    </h3>

                    <p className="mt-1 font-mono text-xs text-primary/90 font-medium">
                      {step.summary}
                    </p>

                    <p className="mt-3 text-sm leading-relaxed text-ink-muted">
                      {step.description}
                    </p>
                  </div>

                  <div className="mt-5 pt-3 border-t border-white/10 flex items-center justify-between text-xs text-ink-muted">
                    <span className="font-mono uppercase tracking-wider">Candidate Hub</span>
                    <span className="text-primary opacity-0 transition-opacity group-hover:opacity-100 flex items-center gap-1 font-semibold">
                      Explore <ArrowRight className="h-3 w-3" />
                    </span>
                  </div>
                </div>
              </StaggerItem>
            );
          })}
        </Stagger>

        {/* Bottom Callout Banner */}
        <Reveal delay={0.2}>
          <div className="mt-12 rounded-3xl border border-white/10 bg-white/[0.03] p-8 sm:p-10 flex flex-col md:flex-row items-center justify-between gap-6 backdrop-blur-sm">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/20 text-primary">
                <Sparkles className="h-6 w-6" />
              </div>
              <div>
                <h4 className="text-lg font-bold text-ink-foreground">
                  Ready to discover your next remote tech opportunity?
                </h4>
                <p className="mt-1 text-sm text-ink-muted">
                  Create your profile in 2 minutes, upload your resume, and start exploring matched jobs.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0 w-full md:w-auto">
              <Link
                href="/auth/candidate/signup"
                className="w-full md:w-auto inline-flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
              >
                <span>Create Candidate Profile</span>
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
