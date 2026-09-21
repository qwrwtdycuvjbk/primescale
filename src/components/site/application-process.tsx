"use client";

import React from "react";
import Link from "next/link";
import {
  Search,
  FileText,
  LogIn,
  UserCheck,
  Sparkles,
  ExternalLink,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import {
  appContainerClass,
  siteEyebrowClass,
  siteHeadlineClass,
  siteBodyClass,
} from "@/components/site/layout";
import { Reveal, Stagger, StaggerItem } from "@/components/site/reveal";

const steps = [
  {
    step: "01",
    title: "Explore Jobs",
    icon: Search,
    description:
      "Browse available verified tech jobs on People Remotely. Explore remote, hybrid, and specialized roles without needing to create an account first.",
    highlights: ["Public job browsing", "Remote & hybrid roles", "No signup required to view"],
  },
  {
    step: "02",
    title: "View Job Details",
    icon: FileText,
    description:
      "Click 'View Job Details' on any role to inspect full information including job title, company, location, work mode, compensation, required skills, and job source.",
    highlights: ["Detailed job descriptions", "Salary & tech stack info", "Verified source transparency"],
  },
  {
    step: "03",
    title: "Create Account / Sign In",
    icon: LogIn,
    description:
      "When you're ready to access protected job specifics or candidate features, sign in using your existing account or create a new one with email/password or Google.",
    highlights: ["Email & password login", "1-click Google Sign-in", "Secure authentication"],
  },
  {
    step: "04",
    title: "Complete Your Profile",
    icon: UserCheck,
    description:
      "Fill in your candidate profile with your experience, role preferences, and upload your required resume. This enables People Remotely to match you with suitable open positions.",
    highlights: ["Target role & experience", "Resume file upload", "Enables job matching"],
  },
  {
    step: "05",
    title: "Review Job Matches",
    icon: Sparkles,
    description:
      "Access your candidate dashboard to view qualified job matches tailored to your profile data and skills, complete with match scores for transparent relevance.",
    highlights: ["Personalized match feed", "Relevance score breakdown", "Direct match dashboard"],
  },
  {
    step: "06",
    title: "Apply to the Employer",
    icon: ExternalLink,
    description:
      "Review the role requirements and click Apply. For external listings, you are redirected to the employer's official application page to submit directly.",
    highlights: ["Seamless application flow", "Official employer redirect", "Direct recruiter submissions"],
  },
];

export function ApplicationProcess() {
  return (
    <section
      id="how-applications-work"
      className="border-t border-border bg-background py-20 sm:py-28"
    >
      <div className={appContainerClass}>
        {/* Header Block */}
        <Reveal>
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
            <div>
              <div className={siteEyebrowClass}>
                <span className="text-primary font-bold">[02]</span>
                <span>Application Process</span>
                <span className="h-px flex-1 bg-border" />
              </div>
              <h2 className={siteHeadlineClass}>
                How Applications <span className="italic text-primary">Work</span>
              </h2>
              <p className={siteBodyClass}>
                Find relevant opportunities, review the details, and apply directly to the employer.
              </p>
            </div>

            {/* Quick Actions */}
            <div className="flex flex-wrap items-center gap-3 shrink-0">
              <Link
                href="/#departments"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-5 py-2.5 text-sm font-semibold text-foreground transition-all hover:bg-muted hover:border-primary/40"
              >
                <span>Explore Jobs</span>
                <ArrowRight className="h-4 w-4 text-primary" />
              </Link>
              <Link
                href="/auth/candidate/signup"
                className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5"
              >
                <span>Create Profile</span>
              </Link>
            </div>
          </div>
        </Reveal>

        {/* 6-Step Visual Grid */}
        <Stagger className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {steps.map((item) => {
            const IconComponent = item.icon;
            return (
              <StaggerItem key={item.step}>
                <div className="group relative flex h-full flex-col justify-between rounded-3xl border border-border bg-card p-7 transition-all duration-300 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5">
                  {/* Top Bar: Icon + Step Badge */}
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-foreground transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                        <IconComponent className="h-6 w-6" />
                      </div>
                      <span className="font-mono text-xs font-bold uppercase tracking-widest text-muted-foreground group-hover:text-primary">
                        Step {item.step}
                      </span>
                    </div>

                    <h3 className="mt-6 text-xl font-bold tracking-tight text-foreground">
                      {item.title}
                    </h3>
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                      {item.description}
                    </p>
                  </div>

                  {/* Highlights Pill List */}
                  <div className="mt-6 border-t border-border/60 pt-4">
                    <ul className="space-y-1.5">
                      {item.highlights.map((highlight, idx) => (
                        <li
                          key={idx}
                          className="flex items-center gap-2 text-xs font-medium text-foreground/80"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
                          <span>{highlight}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </StaggerItem>
            );
          })}
        </Stagger>
      </div>
    </section>
  );
}
