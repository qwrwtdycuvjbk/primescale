import { ROLE_CATEGORIES } from "@/lib/constants";

export type MatchingSeatStatus = "collecting" | "shortlisting" | "trial";

export type MatchingSeat = {
  id: string;
  title: string;
  stack: string;
  remoteScope: string;
  category: (typeof ROLE_CATEGORIES)[number];
  status: MatchingSeatStatus;
  screeningFor: string;
};

/** Roles People Remotely is actively matching this week (seeded inventory). */
export const MATCHING_SEATS: MatchingSeat[] = [
  {
    id: "fullstack-senior",
    title: "Senior Full-stack Engineer",
    stack: "React, Next.js, TypeScript, Node",
    remoteScope: "US / Canada remote",
    category: "Full-stack",
    status: "shortlisting",
    screeningFor: "Shipped product end to end, strong TypeScript, remote async communication",
  },
  {
    id: "backend-node",
    title: "Backend Engineer",
    stack: "Node.js, PostgreSQL, APIs, cloud",
    remoteScope: "US remote",
    category: "Backend",
    status: "collecting",
    screeningFor: "API design, data modeling, production ownership",
  },
  {
    id: "ai-ml",
    title: "AI / ML Engineer",
    stack: "Python, LLMs, evals, production AI",
    remoteScope: "US / Canada remote",
    category: "AI / ML",
    status: "collecting",
    screeningFor: "Real shipped AI features, not demos-only; evals and reliability mindset",
  },
  {
    id: "devops-platform",
    title: "DevOps / Platform Engineer",
    stack: "AWS, Kubernetes, CI/CD, observability",
    remoteScope: "US remote",
    category: "DevOps",
    status: "shortlisting",
    screeningFor: "Platform ownership, infra-as-code, on-call comfort",
  },
  {
    id: "data-engineer",
    title: "Data Engineer",
    stack: "Python, SQL, warehouses, pipelines",
    remoteScope: "US remote",
    category: "Data",
    status: "collecting",
    screeningFor: "Reliable pipelines, warehouse modeling, stakeholder clarity",
  },
];

export const MATCHING_STATUS_LABEL: Record<MatchingSeatStatus, string> = {
  collecting: "Collecting",
  shortlisting: "Shortlisting",
  trial: "Trial",
};

export const MATCHING_QUEUE_COOKIE = "pr_matching_queue";

export function isRoleCategory(
  value: string | null | undefined,
): value is (typeof ROLE_CATEGORIES)[number] {
  if (!value) return false;
  return (ROLE_CATEGORIES as readonly string[]).includes(value);
}

export function candidateQueueSignupHref(category: string) {
  const params = new URLSearchParams({ queue: category });
  return `/auth/candidate/signup?${params.toString()}`;
}
