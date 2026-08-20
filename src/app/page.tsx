import dynamic from "next/dynamic";
import { SiteHeader } from "@/components/site/site-header";
import { Hero } from "@/components/site/hero";
import { Marquee } from "@/components/site/marquee";

const HowItWorks = dynamic(() =>
  import("@/components/site/how-it-works").then((mod) => mod.HowItWorks),
);
const WhyUs = dynamic(() =>
  import("@/components/site/why-us").then((mod) => mod.WhyUs),
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
      <WhyUs />
      <Comparison />

      <AudienceBlock
        id="for-employers"
        index="05"
        variant="dark"
        eyebrow="For employers"
        title="Post free. Get a shortlist."
        intro="A small vetted set in 24 hours, optional 2-day trial, People Prime for payroll and onboarding."
        bullets={[
          "Free to post a remote tech role",
          "3 to 5 interview-ready matches, not a resume pile",
          "Optional 2-day trial before you commit",
          "Payroll, compliance, and onboarding handled",
        ]}
        ctaLabel="Post a role free"
        ctaHref="/auth/employer/signup"
      />

      <AudienceBlock
        id="for-candidates"
        index="06"
        variant="light"
        eyebrow="For candidates"
        title="One profile. Get matched."
        intro="Build your profile once. We match you to remote tech roles we’re actively filling — not a spam apply button."
        bullets={[
          "AI, Cloud, Data, DevOps, Full-stack, and more",
          "One profile, ongoing matches",
          "Mark roles you want on mutual fit",
          "People Prime for payroll when you place",
        ]}
        ctaLabel="Create candidate profile"
        ctaHref="/auth/candidate/signup"
        reverse
      />

      <GetStarted />
      <SiteFooter />
    </main>
  );
}
