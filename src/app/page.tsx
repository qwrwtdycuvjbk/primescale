import { SiteHeader } from "@/components/site/site-header";
import { Hero } from "@/components/site/hero";
import { Marquee } from "@/components/site/marquee";
import { HowItWorks } from "@/components/site/how-it-works";
import { WhyUs } from "@/components/site/why-us";
import { AudienceBlock } from "@/components/site/audience-block";
import { GetStarted } from "@/components/site/get-started";
import { SiteFooter } from "@/components/site/site-footer";

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
      <WhyUs />

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
        ctaHref="/auth/signup?role=employer"
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
        ctaHref="/auth/signup?role=candidate"
        reverse
      />

      <GetStarted />
      <SiteFooter />
    </main>
  );
}
