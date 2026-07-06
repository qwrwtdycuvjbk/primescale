import { getAppUrl, sendOpsEmail } from "@/lib/ops-email";
import { getServiceClient } from "@/lib/supabase/service";

export const MIN_MATCH_SCORE = 85;

type MatchAlertDetails = {
  matchId: string;
  matchScore: number;
  matchReason?: string;
  jobTitle: string;
  companyName: string;
  candidateName: string;
  candidateEmail: string;
  candidateHeadline?: string;
  candidateSkills: string[];
};

async function loadMatchAlertDetails(
  matchId: string,
): Promise<MatchAlertDetails | null> {
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
        posted_by,
        companies ( name )
      ),
      candidate_profiles (
        headline,
        skills,
        profiles ( full_name, email )
      )
    `,
    )
    .eq("id", matchId)
    .single();

  if (!match?.jobs) return null;

  const jobRaw = match.jobs;
  const job = (Array.isArray(jobRaw) ? jobRaw[0] : jobRaw) as {
    title: string;
    companies?: { name: string } | { name: string }[] | null;
  };
  const companyRaw = job.companies;
  const company = Array.isArray(companyRaw) ? companyRaw[0] : companyRaw;

  const candidateRaw = match.candidate_profiles;
  const candidate = (Array.isArray(candidateRaw) ? candidateRaw[0] : candidateRaw) as {
    headline?: string;
    skills?: string[];
    profiles?:
      | { full_name: string; email: string }
      | { full_name: string; email: string }[];
  } | null;

  const profileRaw = candidate?.profiles;
  const profile = Array.isArray(profileRaw) ? profileRaw[0] : profileRaw;
  if (!profile) return null;

  return {
    matchId,
    matchScore: match.match_score,
    matchReason: match.match_reason ?? undefined,
    jobTitle: job.title,
    companyName: company?.name ?? "Company",
    candidateName: profile.full_name,
    candidateEmail: profile.email,
    candidateHeadline: candidate?.headline ?? undefined,
    candidateSkills: candidate?.skills ?? [],
  };
}

function buildMatchAlertHtml(details: MatchAlertDetails) {
  const appUrl = getAppUrl();
  const skills = details.candidateSkills.slice(0, 12).join(", ") || "—";

  return `
    <h2>High-confidence match — recruiter review needed</h2>
    <p>A candidate scored <strong>${details.matchScore}%</strong> for a role. Review before the employer sees this match.</p>
    <h3>Role</h3>
    <ul>
      <li><strong>Title:</strong> ${details.jobTitle}</li>
      <li><strong>Company:</strong> ${details.companyName}</li>
    </ul>
    <h3>Candidate</h3>
    <ul>
      <li><strong>Name:</strong> ${details.candidateName}</li>
      <li><strong>Email:</strong> ${details.candidateEmail}</li>
      <li><strong>Headline:</strong> ${details.candidateHeadline ?? "—"}</li>
      <li><strong>Skills:</strong> ${skills}</li>
    </ul>
    ${details.matchReason ? `<p><strong>Match reason:</strong> ${details.matchReason}</p>` : ""}
    <p><a href="${appUrl}/admin/matches">Review in PrimeScale</a></p>
  `;
}

async function sendMatchAlertEmail(details: MatchAlertDetails) {
  return sendOpsEmail(
    `Review match (${details.matchScore}%): ${details.candidateName} → ${details.jobTitle} @ ${details.companyName}`,
    buildMatchAlertHtml(details),
  );
}

export async function notifyRecruitersForHighMatch(matchId: string) {
  const supabase = getServiceClient();
  if (!supabase) return;

  const { data: match } = await supabase
    .from("matches")
    .select("id, match_score, recruiter_notified_at")
    .eq("id", matchId)
    .single();

  if (!match || match.match_score < MIN_MATCH_SCORE || match.recruiter_notified_at) {
    return;
  }

  const details = await loadMatchAlertDetails(matchId);
  const emailed = details ? await sendMatchAlertEmail(details) : false;

  await supabase
    .from("matches")
    .update({
      recruiter_notified_at: emailed ? new Date().toISOString() : null,
      updated_at: new Date().toISOString(),
    })
    .eq("id", matchId);
}
