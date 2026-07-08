import dynamic from "next/dynamic";
import { SiteHeader } from "@/components/site/site-header";
import { Hero } from "@/components/site/hero";
import { Marquee } from "@/components/site/marquee";

const HowItWorks = dynamic(() =>
  import("@/components/site/how-it-works").then((mod) => mod.HowItWorks),
);
const Comparison = dynamic(() =>
  import("@/components/site/comparison").then((mod) => mod.Comparison),
);
const AudienceBlock = dynamic(() =>
  import("@/components/site/audience-block").then((mod) => mod.AudienceBlock),
);
const GetStarted = dynamic(() =>
  import("@/components/site/get-started").then((mod) => mod.GetStarted),
);
const SiteFooter = dynamic(() =>
  import("@/components/site/site-footer").then((mod) => mod.SiteFooter),
);

const marqueeItems = [
  "AI / ML",
  "Cloud",
  "Data",
  "DevOps",
  "Cybersecurity",
  "Full-stack",
  "Backend",
  "Frontend",
];

export default function Home() {
  return (
    <main className="bg-background">
      <SiteHeader />
      <Hero />

      <div className="border-y border-border bg-primary py-5 text-primary-foreground">
        <Marquee items={marqueeItems} duration={36} />
      </div>

      <HowItWorks />
      <Comparison />

      <AudienceBlock
        id="for-employers"
        index="04"
        variant="dark"
        eyebrow="For employers"
        title="Post a role. Get matched candidates."
        intro="Skip the job board chaos. Post a US remote tech role, get AI-matched candidates, and shortlist from your dashboard with People Prime as your staffing backstop."
        bullets={[
          "AI-assisted job description parsing",
          "Skill and seniority-based matching",
          "US remote tech roles only",
          "Shortlist candidates from your dashboard",
        ]}
        ctaLabel="Post a role for free"
        ctaHref="/auth/employer/signup"
      />

      <AudienceBlock
        id="for-candidates"
        index="05"
        variant="light"
        eyebrow="For candidates"
        title="Build your profile. Get matched."
        intro="One profile, zero spam. Add your skills and US work authorization, and let PrimeScale surface remote tech roles that actually fit."
        bullets={[
          "One profile, ongoing matches",
          "US remote tech roles only",
          "AI scoring against real employer needs",
          "Mark roles you are interested in",
        ]}
        ctaLabel="Create your profile"
        ctaHref="/auth/candidate/signup"
        reverse
      />

      <GetStarted />
      <SiteFooter />
    </main>
  );
}
