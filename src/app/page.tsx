import dynamic from "next/dynamic";
import { SiteHeader } from "@/components/site/site-header";
import { Hero } from "@/components/site/hero";
import { Marquee } from "@/components/site/marquee";

const USRemoteJobs = dynamic(() =>
  import("@/components/site/us-remote-jobs").then((mod) => mod.USRemoteJobs),
);
const RemoteHybridJobs = dynamic(() =>
  import("@/components/site/remote-hybrid-jobs").then((mod) => mod.RemoteHybridJobs),
);
const DepartmentJobs = dynamic(() =>
  import("@/components/site/department-jobs").then((mod) => mod.DepartmentJobs),
);
const ApplicationProcess = dynamic(() =>
  import("@/components/site/application-process").then((mod) => mod.ApplicationProcess),
);
const DashboardWorkflow = dynamic(() =>
  import("@/components/site/dashboard-workflow").then((mod) => mod.DashboardWorkflow),
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

      <ApplicationProcess />

      <DashboardWorkflow />

      <DepartmentJobs />

      <USRemoteJobs />

      <RemoteHybridJobs />

      <SiteFooter />
    </main>
  );
}
