"use client";

import React from "react";
import Link from "next/link";
import { Search, User, FileText, Sparkles, Send, ArrowRight } from "lucide-react";
import { appContainerClass } from "@/components/site/layout";
import { Reveal, Stagger, StaggerItem } from "@/components/site/reveal";

const steps = [
  {
    step: "01",
    title: "Explore Opportunities",
    icon: <Search className="h-5 w-5 text-[#191f1e] stroke-[1.75]" />,
    description:
      "Browse jobs without an account. Review requirements, location, and salary when available.",
  },
  {
    step: "02",
    title: "Create Your Profile",
    icon: <User className="h-5 w-5 text-[#191f1e] stroke-[1.75]" />,
    description:
      "Sign up, upload your resume, and add your experience and job preferences.",
  },
  {
    step: "03",
    title: "Discover Your Matches",
    icon: (
      <div className="relative flex items-center justify-center">
        <FileText className="h-5 w-5 text-[#191f1e] stroke-[1.75]" />
        <Sparkles className="absolute -right-1 -top-1 h-3 w-3 fill-[#191f1e]/20 text-[#191f1e] stroke-[1.75]" />
      </div>
    ),
    description:
      "Find opportunities tailored to your profile and review match scores in your dashboard.",
  },
  {
    step: "04",
    title: "Apply and Stay Organized",
    icon: (
      <Send className="h-5 w-5 -translate-x-0.5 translate-y-0.5 text-[#191f1e] stroke-[1.75]" />
    ),
    description:
      "Follow the listing to apply. External jobs open on the employer’s website. Organize your applications in your dashboard.",
  },
];

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="relative border-t border-border/40 bg-[#fbfbf8] py-20 text-foreground sm:py-28"
    >
      {/* Anchor targets to preserve existing header navigation behavior */}
      <div id="how-applications-work" className="absolute -top-20" />
      <div id="dashboard-workflow" className="absolute -top-20" />

      <div className={appContainerClass}>
        {/* Section Heading */}
        <Reveal className="text-center">
          <div className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">
            <span className="font-bold text-[#9ec816]">[02]</span>
            <span>HOW IT WORKS</span>
          </div>

          <h2 className="display-headline mt-4 text-center text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
            <span className="block">Your Next Opportunity</span>
            <span className="mt-1 block italic text-[#9ec816] sm:mt-2">
              Starts Here
            </span>
          </h2>

          <p className="mx-auto mt-4 max-w-2xl text-center text-base leading-relaxed text-muted-foreground sm:text-lg">
            Explore jobs, get personalized matches, and manage your search in one place.
          </p>
        </Reveal>

        {/* Four Feature Cards */}
        <Stagger className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((item) => (
            <StaggerItem key={item.step}>
              <div className="group flex h-full flex-col justify-between rounded-2xl border border-border/70 bg-white p-6 shadow-xs transition-all duration-300 hover:border-[#9ec816]/50 hover:shadow-md sm:p-7">
                <div>
                  {/* Circular Icon Container */}
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#eef8be] transition-transform duration-300 group-hover:scale-105">
                    {item.icon}
                  </div>

                  {/* Number Label */}
                  <span className="mt-6 block font-mono text-xs font-medium tracking-wider text-muted-foreground">
                    {item.step}
                  </span>

                  {/* Card Title */}
                  <h3 className="display-headline mt-2 text-xl font-bold tracking-tight text-foreground sm:text-2xl">
                    {item.title}
                  </h3>

                  {/* Card Description */}
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {item.description}
                  </p>
                </div>
              </div>
            </StaggerItem>
          ))}
        </Stagger>

        {/* Call to Action Buttons */}
        <Reveal delay={0.2} className="mt-12 flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/#departments"
            className="inline-flex items-center gap-2 rounded-full bg-[#d5ec64] px-7 py-3.5 text-sm font-semibold text-[#191f1e] shadow-sm transition-transform duration-200 hover:-translate-y-0.5 hover:bg-[#cbe257]"
          >
            <span>Explore Jobs</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/auth/candidate/signup"
            className="inline-flex items-center gap-2 rounded-full border border-black/15 bg-white px-7 py-3.5 text-sm font-semibold text-[#191f1e] transition-all duration-200 hover:border-black/30 hover:bg-muted/50"
          >
            <span>Create Profile</span>
          </Link>
        </Reveal>
      </div>
    </section>
  );
}
