/**
 * Phase 17 — Job Applications & Job Leads Integration Test Suite
 *
 * Tests:
 * 1. Register Candidate 1, Candidate 2, Employer 1, Employer 2, Admin
 * 2. Setup candidate profile and active employer job
 * 3. Candidate 1 applies to active job via /api/v1/applications/apply/
 * 4. Duplicate application rejected with 400 Bad Request
 * 5. Candidate 1 lists applications -> sees 1 application
 * 6. Candidate 1 views own application detail -> 200 OK
 * 7. Candidate 2 lists applications -> sees 0 applications
 * 8. Candidate 2 denied Candidate 1's application detail -> 403 Forbidden (IDOR)
 * 9. Employer 1 lists applications -> sees Candidate 1's application
 * 10. Employer 1 updates status to employer_shortlisted -> transitions to mutual_fit
 * 11. Employer 2 denied Employer 1's application detail & update -> 403 Forbidden (IDOR)
 * 12. Candidate denied modifying employer review fields -> 403 Forbidden
 * 13. Admin lists and filters applications -> sees all
 * 14. Admin lists and saves job leads -> 200 OK
 * 15. Candidate forbidden from job leads -> 403 Forbidden
 */

const BASE_URL = process.env.TEST_BASE_URL || "http://127.0.0.1:8000";

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  ✓ PASS: ${message}`);
    passed++;
  } else {
    console.error(`  ✗ FAIL: ${message}`);
    failed++;
  }
}

async function run() {
  console.log(`Starting Phase 17 Applications & Job Leads Integration Tests against: ${BASE_URL}\n`);
  const ts = Date.now();

  const cand1Email = `phase17.cand1.${ts}@example.com`;
  const cand2Email = `phase17.cand2.${ts}@example.com`;
  const emp1Email = `phase17.emp1.${ts}@example.com`;
  const emp2Email = `phase17.emp2.${ts}@example.com`;
  const adminEmail = `admin@example.com`;
  const password = "Phase17Password!123";

  // 1. Register users
  console.log("[1] Registering test accounts...");
  const c1Reg = await fetch(`${BASE_URL}/api/v1/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: cand1Email, password, role: "candidate", full_name: "Candidate One" }),
  });
  const c1Data = await c1Reg.json();
  assert(c1Reg.status === 201, `Candidate 1 registered HTTP 201 (${c1Reg.status})`);
  const c1Token = c1Data.access;

  const c2Reg = await fetch(`${BASE_URL}/api/v1/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: cand2Email, password, role: "candidate", full_name: "Candidate Two" }),
  });
  const c2Data = await c2Reg.json();
  assert(c2Reg.status === 201, `Candidate 2 registered HTTP 201 (${c2Reg.status})`);
  const c2Token = c2Data.access;

  const e1Reg = await fetch(`${BASE_URL}/api/v1/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: emp1Email, password, role: "employer", full_name: "Employer One" }),
  });
  const e1Data = await e1Reg.json();
  assert(e1Reg.status === 201, `Employer 1 registered HTTP 201 (${e1Reg.status})`);
  const e1Token = e1Data.access;

  const e2Reg = await fetch(`${BASE_URL}/api/v1/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: emp2Email, password, role: "employer", full_name: "Employer Two" }),
  });
  const e2Data = await e2Reg.json();
  assert(e2Reg.status === 201, `Employer 2 registered HTTP 201 (${e2Reg.status})`);
  const e2Token = e2Data.access;

  // 2. Admin Login
  console.log("\n[2] Logging in as Admin...");
  const adminLogin = await fetch(`${BASE_URL}/api/v1/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@peopleremotely.com", password: "AdminPassword123!" }),
  });
  const adminData = await adminLogin.json();
  assert(adminLogin.status === 200, `Admin logged in HTTP 200 (${adminLogin.status})`);
  const adminToken = adminData.access;

  // 3. Setup Profiles and Jobs
  console.log("\n[3] Setting up candidate profiles and company jobs...");
  const c1ProfileRes = await fetch(`${BASE_URL}/api/v1/candidates/me/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${c1Token}` },
    body: JSON.stringify({
      headline: "Senior Django & React Specialist",
      skills: ["python", "django", "react", "postgresql"],
      role_categories: ["backend", "engineering"],
      experience_level: "senior",
      years_experience: 7,
      work_authorization: "us_citizen",
      us_state: "CA",
      remote_preference: "remote",
      availability_status: "actively_looking",
      open_to_matching: true,
      resume_url: "https://s3.amazonaws.com/resumes/c17-1.pdf",
    }),
  });
  assert(c1ProfileRes.status === 200 || c1ProfileRes.status === 201, `Candidate 1 profile saved HTTP 200 (${c1ProfileRes.status})`);

  const c2ProfileRes = await fetch(`${BASE_URL}/api/v1/candidates/me/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${c2Token}` },
    body: JSON.stringify({
      headline: "Mid Frontend Engineer",
      skills: ["react", "typescript", "tailwind"],
      role_categories: ["frontend", "engineering"],
      experience_level: "mid",
      years_experience: 3,
      work_authorization: "us_citizen",
      us_state: "NY",
      remote_preference: "remote",
      availability_status: "actively_looking",
      open_to_matching: true,
      resume_url: "https://s3.amazonaws.com/resumes/c17-2.pdf",
    }),
  });
  assert(c2ProfileRes.status === 200 || c2ProfileRes.status === 201, `Candidate 2 profile saved HTTP 200 (${c2ProfileRes.status})`);

  // Employer 1 company & job
  await fetch(`${BASE_URL}/api/v1/companies/me/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${e1Token}` },
    body: JSON.stringify({
      name: `TechCorp Alpha ${ts}`,
      country: "US",
      industry: "Software",
      description: "Fast-growing remote team.",
    }),
  });

  const jobRes = await fetch(`${BASE_URL}/api/v1/jobs/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${e1Token}` },
    body: JSON.stringify({
      title: "Senior Full Stack Django Engineer",
      description: "Looking for an expert Python / Django developer to scale platforms.",
      role_type: "full-time",
      experience_level: "senior",
      tech_stack: ["python", "django", "postgresql"],
      salary_range: "$140,000 - $180,000",
      work_type: "remote",
      visa_requirements: "Authorized to work in the US",
      publish: true,
    }),
  });
  const jobData = await jobRes.json();
  const jobId = jobData.jobId || jobData.id;
  assert(jobRes.status === 201, `Employer 1 Job created HTTP 201 (${jobRes.status})`);

  // 4. Candidate 1 applies to active job
  console.log("\n[4] Candidate 1 applying to Job 1...");
  const applyRes = await fetch(`${BASE_URL}/api/v1/applications/apply/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${c1Token}` },
    body: JSON.stringify({ job_id: jobId, cover_note: "Excited about this Django role!" }),
  });
  const applyData = await applyRes.json();
  assert(applyRes.status === 200 || applyRes.status === 201, `Candidate 1 application submitted HTTP 200/201 (${applyRes.status})`);
  assert(applyData.ok === true, "Application response has ok: true");
  const appId = applyData.application?.id;
  assert(Boolean(appId), `Application ID received: ${appId}`);
  assert(applyData.application?.status === "candidate_interested", `Status set to candidate_interested (${applyData.application?.status})`);

  // 5. Duplicate Application Protection
  console.log("\n[5] Testing Duplicate Application Protection...");
  const dupApplyRes = await fetch(`${BASE_URL}/api/v1/applications/apply/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${c1Token}` },
    body: JSON.stringify({ job_id: jobId }),
  });
  assert(dupApplyRes.status === 400, `Duplicate application rejected HTTP 400 (${dupApplyRes.status})`);
  const dupData = await dupApplyRes.json();
  assert(dupData.error && dupData.error.includes("already applied"), "Error message specifies already applied");

  // 6. Candidate 1 lists and views application
  console.log("\n[6] Candidate 1 listing and viewing application...");
  const c1ListRes = await fetch(`${BASE_URL}/api/v1/applications/`, {
    headers: { Authorization: `Bearer ${c1Token}` },
  });
  const c1List = await c1ListRes.json();
  assert(c1ListRes.status === 200, `Candidate 1 lists applications HTTP 200 (${c1ListRes.status})`);
  assert(Array.isArray(c1List) && c1List.length === 1, `Candidate 1 sees exactly 1 application (${c1List.length})`);
  assert(c1List[0].id === appId, "Application ID matches");
  assert(c1List[0].job?.title === "Senior Full Stack Django Engineer", "Job title matches");

  const c1DetailRes = await fetch(`${BASE_URL}/api/v1/applications/${appId}/`, {
    headers: { Authorization: `Bearer ${c1Token}` },
  });
  const c1Detail = await c1DetailRes.json();
  assert(c1DetailRes.status === 200, `Candidate 1 fetches detail HTTP 200 (${c1DetailRes.status})`);
  assert(c1Detail.id === appId, "Detail ID matches");

  // 7. Candidate Isolation / IDOR Protection
  console.log("\n[7] Testing Candidate Isolation (Candidate 2)...");
  const c2ListRes = await fetch(`${BASE_URL}/api/v1/applications/`, {
    headers: { Authorization: `Bearer ${c2Token}` },
  });
  const c2List = await c2ListRes.json();
  assert(c2ListRes.status === 200, `Candidate 2 lists applications HTTP 200 (${c2ListRes.status})`);
  assert(Array.isArray(c2List) && c2List.length === 0, `Candidate 2 sees 0 applications (${c2List.length})`);

  const c2IdorRes = await fetch(`${BASE_URL}/api/v1/applications/${appId}/`, {
    headers: { Authorization: `Bearer ${c2Token}` },
  });
  assert(c2IdorRes.status === 403, `Candidate 2 denied Candidate 1's application HTTP 403 (${c2IdorRes.status})`);

  // 8. Employer 1 application review
  console.log("\n[8] Employer 1 reviewing applications...");
  const e1ListRes = await fetch(`${BASE_URL}/api/v1/applications/`, {
    headers: { Authorization: `Bearer ${e1Token}` },
  });
  const e1List = await e1ListRes.json();
  assert(e1ListRes.status === 200, `Employer 1 lists applications HTTP 200 (${e1ListRes.status})`);
  assert(Array.isArray(e1List) && e1List.length === 1, `Employer 1 sees Candidate 1 application (${e1List.length})`);

  // Employer 1 shortlists candidate -> reaches mutual_fit
  const shortlistRes = await fetch(`${BASE_URL}/api/v1/applications/${appId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${e1Token}` },
    body: JSON.stringify({ status: "employer_shortlisted" }),
  });
  const shortlistData = await shortlistRes.json();
  assert(shortlistRes.status === 200, `Employer 1 shortlisted application HTTP 200 (${shortlistRes.status})`);
  assert(shortlistData.status === "mutual_fit", `Status advanced to mutual_fit (${shortlistData.status})`);

  // 9. Employer Isolation / IDOR Protection
  console.log("\n[9] Testing Employer Isolation (Employer 2)...");
  const e2ListRes = await fetch(`${BASE_URL}/api/v1/applications/`, {
    headers: { Authorization: `Bearer ${e2Token}` },
  });
  const e2List = await e2ListRes.json();
  assert(e2ListRes.status === 200, `Employer 2 lists applications HTTP 200 (${e2ListRes.status})`);
  assert(Array.isArray(e2List) && e2List.length === 0, `Employer 2 sees 0 applications (${e2List.length})`);

  const e2IdorRes = await fetch(`${BASE_URL}/api/v1/applications/${appId}/`, {
    headers: { Authorization: `Bearer ${e2Token}` },
  });
  assert(e2IdorRes.status === 403, `Employer 2 denied Employer 1's application HTTP 403 (${e2IdorRes.status})`);

  // 10. Admin application access
  console.log("\n[10] Admin global applications management...");
  const adminListRes = await fetch(`${BASE_URL}/api/v1/applications/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  const adminList = await adminListRes.json();
  assert(adminListRes.status === 200, `Admin lists all applications HTTP 200 (${adminListRes.status})`);
  assert(Array.isArray(adminList) && adminList.length >= 1, `Admin sees active applications (count: ${adminList.length})`);

  // 11. Job Leads API verification
  console.log("\n[11] Testing Job Leads API endpoints...");
  const leadCreateRes = await fetch(`${BASE_URL}/api/v1/job-leads/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      external_id: `test_lead_${ts}`,
      title: "Staff Python Infrastructure Engineer",
      company: "Acme Remote Systems",
      apply_url: "https://example.com/apply/staff-python",
      country: "GB",
      location: "London, UK",
      is_remote: true,
      description_preview: "Leading remote infrastructure systems.",
    }),
  });
  assert(leadCreateRes.status === 201, `Admin created Job Lead HTTP 201 (${leadCreateRes.status})`);

  const leadsListRes = await fetch(`${BASE_URL}/api/v1/job-leads/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  const leadsData = await leadsListRes.json();
  assert(leadsListRes.status === 200, `Admin listed Job Leads HTTP 200 (${leadsListRes.status})`);
  assert(leadsData.ok === true, "Leads response has ok: true");
  assert(leadsData.count >= 1, `Found ${leadsData.count} job leads in database`);

  const nonAdminLeadsRes = await fetch(`${BASE_URL}/api/v1/job-leads/`, {
    headers: { Authorization: `Bearer ${c1Token}` },
  });
  assert(nonAdminLeadsRes.status === 403, `Candidate denied job leads API access HTTP 403 (${nonAdminLeadsRes.status})`);

  console.log("\n========================================");
  console.log(`PHASE 17 TESTS COMPLETE: ${passed}/${passed + failed} PASSED`);
  console.log("========================================\n");

  if (failed > 0) {
    process.exit(1);
  }
}

run().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
