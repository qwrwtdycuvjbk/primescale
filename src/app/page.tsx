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

      <div className="border-y border-border bg-primary py-3 text-primary-foreground">
        <Marquee items={marqueeItems} duration={36} />
      </div>

      <HowItWorks />
      <Comparison />

      <AudienceBlock
        id="for-employers"
        index="04"
        variant="dark"
        eyebrow="For employers"
        title="Post a role. Get matches."
        intro="US remote tech only. Recruiter-reviewed candidates in your dashboard, with People Prime as your staffing backstop."
        bullets={[
          "AI-assisted JD parsing",
          "Skill and seniority matching",
          "US remote tech roles only",
          "Shortlist from one dashboard",
        ]}
        ctaLabel="Post a role free"
        ctaHref="/auth/employer/signup"
      />

      <AudienceBlock
        id="for-candidates"
        index="05"
        variant="light"
        eyebrow="For candidates"
        title="One profile. Ongoing matches."
        intro="Add skills and work auth once. See US remote tech roles that fit — no spam."
        bullets={[
          "One profile, ongoing matches",
          "US remote tech roles only",
          "Skill and seniority matching",
          "Mark roles you want",
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
