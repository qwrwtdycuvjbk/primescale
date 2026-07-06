import { getAppUrl, sendOpsEmail } from "@/lib/ops-email";
import { getServiceClient } from "@/lib/supabase/service";
import type { HandoffRequest, MatchStatus } from "@/lib/types";

export function resolveMatchStatus(
  currentStatus: MatchStatus,
  requestedStatus: MatchStatus,
): MatchStatus {
  if (requestedStatus === "rejected") return "rejected";

  const isMutualFit =
    (requestedStatus === "employer_shortlisted" &&
      currentStatus === "candidate_interested") ||
    (requestedStatus === "candidate_interested" &&
      currentStatus === "employer_shortlisted");

  if (isMutualFit) return "mutual_fit";
  return requestedStatus;
}

type HandoffDetails = {
  matchId: string;
  matchScore: number;
  matchReason?: string;
  jobTitle: string;
  companyName: string;
  salaryRange?: string;
  employerName: string;
  employerEmail: string;
  employerPhone?: string;
  candidateName: string;
  candidateEmail: string;
  candidatePhone?: string;
  candidateHeadline?: string;
  candidateSkills: string[];
  linkedinUrl?: string;
  githubUrl?: string;
  resumeUrl?: string;
};

async function loadHandoffDetails(matchId: string): Promise<HandoffDetails | null> {
  const supabase = getServiceClient();
  if (!supabase) return null;

  const { data: match } = await supabase
    .from("matches")
    .select(
      `
      id,
      match_score,
      match_reason,
      jobs (
        title,
        salary_range,
        posted_by,
        companies ( name )
      ),
      candidate_profiles (
        headline,
        skills,
        linkedin_url,
        github_url,
        resume_url,
        profiles ( full_name, email, phone )
      )
    `,
    )
    .eq("id", matchId)
    .single();

  if (!match?.jobs) return null;

  const jobRaw = match.jobs;
  const job = (Array.isArray(jobRaw) ? jobRaw[0] : jobRaw) as {
    title: string;
    salary_range?: string;
    posted_by: string;
    companies?: { name: string } | { name: string }[] | null;
  } | null;
  if (!job) return null;

  const companyRaw = job.companies;
  const company = Array.isArray(companyRaw) ? companyRaw[0] : companyRaw;

  const candidateRaw = match.candidate_profiles;
  const candidate = (Array.isArray(candidateRaw) ? candidateRaw[0] : candidateRaw) as {
    headline?: string;
    skills?: string[];
    linkedin_url?: string;
    github_url?: string;
    resume_url?: string;
    profiles?: { full_name: string; email: string; phone?: string } | { full_name: string; email: string; phone?: string }[];
  } | null;

  const { data: employer } = await supabase
    .from("profiles")
    .select("full_name, email, phone")
    .eq("id", job.posted_by)
    .single();

  const candidateProfileRaw = candidate?.profiles;
  const candidateProfile = Array.isArray(candidateProfileRaw)
    ? candidateProfileRaw[0]
    : candidateProfileRaw;

  if (!employer || !candidateProfile) return null;

  return {
    matchId,
    matchScore: match.match_score,
    matchReason: match.match_reason ?? undefined,
    jobTitle: job.title,
    companyName: company?.name ?? "Company",
    salaryRange: job.salary_range ?? undefined,
    employerName: employer.full_name,
    employerEmail: employer.email,
    employerPhone: employer.phone ?? undefined,
    candidateName: candidateProfile.full_name,
    candidateEmail: candidateProfile.email,
    candidatePhone: candidateProfile.phone ?? undefined,
    candidateHeadline: candidate?.headline ?? undefined,
    candidateSkills: candidate?.skills ?? [],
    linkedinUrl: candidate?.linkedin_url ?? undefined,
    githubUrl: candidate?.github_url ?? undefined,
    resumeUrl: candidate?.resume_url ?? undefined,
  };
}

function buildHandoffEmailHtml(details: HandoffDetails) {
  const appUrl = getAppUrl();
  const skills = details.candidateSkills.slice(0, 12).join(", ") || "—";

  return `
    <h2>Mutual fit — People Prime handoff</h2>
    <p>A candidate and employer both expressed interest on PrimeScale.</p>
    <h3>Role</h3>
    <ul>
      <li><strong>Title:</strong> ${details.jobTitle}</li>
      <li><strong>Company:</strong> ${details.companyName}</li>
      <li><strong>Salary:</strong> ${details.salaryRange ?? "—"}</li>
      <li><strong>Match score:</strong> ${details.matchScore}%</li>
    </ul>
    <h3>Employer contact</h3>
    <ul>
      <li><strong>Name:</strong> ${details.employerName}</li>
      <li><strong>Email:</strong> ${details.employerEmail}</li>
      <li><strong>Phone:</strong> ${details.employerPhone ?? "—"}</li>
    </ul>
    <h3>Candidate</h3>
    <ul>
      <li><strong>Name:</strong> ${details.candidateName}</li>
      <li><strong>Email:</strong> ${details.candidateEmail}</li>
      <li><strong>Phone:</strong> ${details.candidatePhone ?? "—"}</li>
      <li><strong>Headline:</strong> ${details.candidateHeadline ?? "—"}</li>
      <li><strong>Skills:</strong> ${skills}</li>
      <li><strong>LinkedIn:</strong> ${details.linkedinUrl ?? "—"}</li>
      <li><strong>GitHub:</strong> ${details.githubUrl ?? "—"}</li>
      <li><strong>Resume:</strong> ${details.resumeUrl ?? "—"}</li>
    </ul>
    ${details.matchReason ? `<p><strong>Match reason:</strong> ${details.matchReason}</p>` : ""}
    <p><a href="${appUrl}/admin/handoffs">Open handoff queue</a></p>
  `;
}

export async function sendHandoffEmail(details: HandoffDetails) {
  return sendOpsEmail(
    `Mutual fit: ${details.candidateName} ↔ ${details.companyName} — ${details.jobTitle}`,
    buildHandoffEmailHtml(details),
  );
}

export async function createMutualFitHandoff(matchId: string) {
  const supabase = getServiceClient();
  if (!supabase) {
    console.warn("SUPABASE_SERVICE_ROLE_KEY not set; cannot create handoff");
    return null;
  }

  const { data: existing } = await supabase
    .from("handoff_requests")
    .select("id")
    .eq("match_id", matchId)
    .maybeSingle();

  if (existing) return existing;

  const details = await loadHandoffDetails(matchId);
  const emailed = details ? await sendHandoffEmail(details) : false;

  const { data: handoff, error } = await supabase
    .from("handoff_requests")
    .insert({
      match_id: matchId,
      status: "pending",
      notified_at: emailed ? new Date().toISOString() : null,
    })
    .select("*")
    .single();

  if (error) {
    console.error("Failed to create handoff request", error.message);
    return null;
  }

  return handoff as HandoffRequest;
}
