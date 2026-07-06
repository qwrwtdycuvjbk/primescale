import { getAppUrl, sendOpsEmail } from "@/lib/ops-email";
import { getServiceClient } from "@/lib/supabase/service";

export async function notifyRecruitersJobPosted(jobId: string) {
  const supabase = getServiceClient();
  if (!supabase) return;

  const { data: job } = await supabase
    .from("jobs")
    .select(
      `
      id,
      title,
      description,
      role_type,
      experience_level,
      tech_stack,
      salary_range,
      work_type,
      visa_requirements,
      companies ( name, website, industry ),
      profiles:posted_by ( full_name, email, phone )
    `,
    )
    .eq("id", jobId)
    .single();

  if (!job) return;

  const companyRaw = job.companies;
  const company = Array.isArray(companyRaw) ? companyRaw[0] : companyRaw;
  const employerRaw = job.profiles;
  const employer = Array.isArray(employerRaw) ? employerRaw[0] : employerRaw;
  const skills = (job.tech_stack as string[] | null)?.join(", ") ?? "—";
  const appUrl = getAppUrl();

  const html = `
    <h2>New role posted on PrimeScale</h2>
    <p>An employer published a US remote tech role. Review matches at <a href="${appUrl}/admin/matches">${appUrl}/admin/matches</a>.</p>
    <h3>Role</h3>
    <ul>
      <li><strong>Title:</strong> ${job.title}</li>
      <li><strong>Company:</strong> ${company?.name ?? "—"}</li>
      <li><strong>Level:</strong> ${job.experience_level}</li>
      <li><strong>Type:</strong> ${job.role_type}</li>
      <li><strong>Salary:</strong> ${job.salary_range ?? "—"}</li>
      <li><strong>Work type:</strong> ${job.work_type}</li>
      <li><strong>Visa / eligibility:</strong> ${job.visa_requirements ?? "—"}</li>
      <li><strong>Skills:</strong> ${skills}</li>
    </ul>
    <h3>Employer contact</h3>
    <ul>
      <li><strong>Name:</strong> ${employer?.full_name ?? "—"}</li>
      <li><strong>Email:</strong> ${employer?.email ?? "—"}</li>
      <li><strong>Phone:</strong> ${employer?.phone ?? "—"}</li>
    </ul>
    <p><strong>Description excerpt:</strong></p>
    <p>${job.description.slice(0, 500)}${job.description.length > 500 ? "…" : ""}</p>
  `;

  await sendOpsEmail(
    `New role posted: ${job.title} @ ${company?.name ?? "Company"}`,
    html,
  );
}
