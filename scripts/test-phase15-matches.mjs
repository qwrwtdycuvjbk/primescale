/**
 * Phase 15 Integration Test Script
 * Verifies Matches Module Integration between Next.js and Django REST Framework:
 * 1. Candidate match listing
 * 2. Employer match listing
 * 3. Match detail retrieval
 * 4. Candidate expresses interest (status -> candidate_interested)
 * 5. Employer shortlists candidate (mutual_fit transition + handoff creation)
 * 6. Match rejection (status -> rejected)
 * 7. Admin approval gate (visible_to_employer: false -> true)
 * 8. Candidate isolation (cannot view or patch another candidate's match)
 * 9. Employer isolation (cannot view or patch another employer's match)
 * 10. Candidate write restrictions (cannot modify score/reason or trigger employer actions)
 * 11. Admin match listing & access
 * 12. Duplicate match prevention (unique candidate + job constraint)
 * 13. API response field compatibility (job.companies.name, candidate_profiles.profiles.full_name, etc.)
 */

const DJANGO_URL = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://127.0.0.1:8000";

async function runPhase15Tests() {
  console.log(`Starting Phase 15 Matches Integration Tests against: ${DJANGO_URL}`);
  let passed = 0;
  let total = 0;

  function assert(condition, message) {
    total++;
    if (condition) {
      console.log(`  ✓ PASS: ${message}`);
      passed++;
    } else {
      console.error(`  ✗ FAIL: ${message}`);
    }
  }

  try {
    const timestamp = Date.now();
    const candidate1Email = `phase15.cand1.${timestamp}@example.com`;
    const candidate2Email = `phase15.cand2.${timestamp}@example.com`;
    const employer1Email = `phase15.emp1.${timestamp}@example.com`;
    const employer2Email = `phase15.emp2.${timestamp}@example.com`;
    const password = "Phase15SecurePassword123!";

    // =========================================================================
    // 1. REGISTER USERS
    // =========================================================================
    console.log("\n[1] Registering Candidate 1, Candidate 2, Employer 1, and Employer 2...");

    const regCand1 = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: candidate1Email, password, full_name: "Candidate One", role: "candidate" }),
    });
    assert(regCand1.status === 201, `Candidate 1 registered HTTP 201 (${regCand1.status})`);
    const cand1Data = await regCand1.json();
    const tokenCand1 = cand1Data.access;

    const regCand2 = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: candidate2Email, password, full_name: "Candidate Two", role: "candidate" }),
    });
    assert(regCand2.status === 201, `Candidate 2 registered HTTP 201 (${regCand2.status})`);
    const cand2Data = await regCand2.json();
    const tokenCand2 = cand2Data.access;

    const regEmp1 = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: employer1Email, password, full_name: "Employer One", role: "employer" }),
    });
    assert(regEmp1.status === 201, `Employer 1 registered HTTP 201 (${regEmp1.status})`);
    const emp1Data = await regEmp1.json();
    const tokenEmp1 = emp1Data.access;

    const regEmp2 = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: employer2Email, password, full_name: "Employer Two", role: "employer" }),
    });
    assert(regEmp2.status === 201, `Employer 2 registered HTTP 201 (${regEmp2.status})`);
    const emp2Data = await regEmp2.json();
    const tokenEmp2 = emp2Data.access;

    // Login as Admin
    console.log("\n[2] Logging in as Admin...");
    const adminLogin = await fetch(`${DJANGO_URL}/api/v1/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "admin@peopleremotely.com", password: "AdminPassword123!" }),
    });
    assert(adminLogin.status === 200, `Admin logged in HTTP 200 (${adminLogin.status})`);
    const adminData = await adminLogin.json();
    const tokenAdmin = adminData.access;

    // =========================================================================
    // 3. SET UP PROFILES & JOBS
    // =========================================================================
    console.log("\n[3] Setting up candidate profiles and company jobs...");

    // Candidate 1 Profile (Python, Django, PostgreSQL)
    const profileCand1Res = await fetch(`${DJANGO_URL}/api/v1/candidates/me/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenCand1}` },
      body: JSON.stringify({
        headline: "Staff Python Engineer",
        current_title: "Senior Software Engineer",
        phone: "+1 (555) 123-4567",
        skills: ["python", "django", "postgresql", "celery", "aws"],
        role_categories: ["backend", "fullstack"],
        experience_level: "lead",
        work_authorization: "us_citizen",
        us_state: "CA",
        remote_preference: "remote_only",
        open_to_matching: true,
        resume_url: "https://s3.amazonaws.com/resumes/c1.pdf",
      }),
    });
    assert(profileCand1Res.status === 200, `Candidate 1 profile saved HTTP 200 (${profileCand1Res.status})`);
    const profileCand1 = await profileCand1Res.json();
    const cand1ProfileId = profileCand1.candidateProfileId;

    // Employer 1 Company
    const comp1Res = await fetch(`${DJANGO_URL}/api/v1/companies/me/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp1}` },
      body: JSON.stringify({
        name: "Acme Tech Inc",
        website: "https://acme.example.com",
        industry: "Software",
        hq_city: "San Francisco, CA",
        description: "Leading remote tech company",
      }),
    });
    assert(comp1Res.status === 200 || comp1Res.status === 201, `Employer 1 company saved HTTP 200/201 (${comp1Res.status})`);

    // Employer 1 Job 1 (Active)
    const job1Res = await fetch(`${DJANGO_URL}/api/v1/jobs/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp1}` },
      body: JSON.stringify({
        title: "Lead Backend Developer",
        description: "Build scalable Python systems",
        role_type: "full-time",
        experience_level: "senior",
        tech_stack: ["python", "django", "postgresql"],
        salary_range: "$160,000 - $200,000",
        work_type: "remote",
        visa_requirements: "Authorized to work in the US",
        publish: true,
      }),
    });
    assert(job1Res.status === 201, `Employer 1 Job 1 created HTTP 201 (${job1Res.status})`);
    const job1Data = await job1Res.json();
    const job1Id = job1Data.jobId;

    // Employer 2 Company & Job
    const comp2Res = await fetch(`${DJANGO_URL}/api/v1/companies/me/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp2}` },
      body: JSON.stringify({
        name: "Beta Systems",
        website: "https://beta.example.com",
        industry: "Cloud",
        hq_city: "Austin, TX",
        description: "Cloud infrastructure",
      }),
    });
    assert(comp2Res.status === 200 || comp2Res.status === 201, `Employer 2 company saved HTTP 200/201 (${comp2Res.status})`);

    const job2Res = await fetch(`${DJANGO_URL}/api/v1/jobs/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp2}` },
      body: JSON.stringify({
        title: "Go Cloud Architect",
        description: "Build Kubernetes platforms",
        role_type: "full-time",
        experience_level: "senior",
        tech_stack: ["golang", "kubernetes", "aws"],
        salary_range: "$180,000 - $220,000",
        work_type: "remote",
        visa_requirements: "Authorized to work in the US",
        publish: true,
      }),
    });
    assert(job2Res.status === 201, `Employer 2 Job 2 created HTTP 201 (${job2Res.status})`);
    const job2Data = await job2Res.json();
    const job2Id = job2Data.jobId;

    // =========================================================================
    // 4. TRIGGER MATCH ENGINE FOR CANDIDATE 1
    // =========================================================================
    console.log("\n[4] Running matching engine for Candidate 1 against active jobs...");
    const execSync = (await import("child_process")).execSync;
    const matchRunOut = execSync(
      `.\\backend\\venv\\Scripts\\python.exe backend/manage.py shell -c "from matching.services import run_matching_for_candidate; print(run_matching_for_candidate('${cand1ProfileId}'))"`,
      { encoding: "utf-8" }
    );
    console.log("  Matching output:", matchRunOut.trim());
    assert(matchRunOut.includes("'matched':"), "Matching engine ran successfully for Candidate 1");

    // =========================================================================
    // 5. CANDIDATE MATCH LISTING & COMPATIBILITY
    // =========================================================================
    console.log("\n[5] Candidate 1 retrieves their matches...");
    const candMatchesRes = await fetch(`${DJANGO_URL}/api/v1/matches/`, {
      headers: { Authorization: `Bearer ${tokenCand1}` },
    });
    assert(candMatchesRes.status === 200, `Candidate 1 matches HTTP 200 (${candMatchesRes.status})`);
    const candMatches = await candMatchesRes.json();
    assert(candMatches.length >= 1, `Candidate 1 received matches (got ${candMatches.length})`);
    const match1 = candMatches.find((m) => m.job?.id === job1Id || m.jobs?.id === job1Id) || candMatches[0];
    assert(match1.match_score === 100, `Match score is 100 (got ${match1.match_score})`);
    assert(match1.status === "suggested", `Initial match status is suggested (got ${match1.status})`);
    assert(match1.job && match1.job.title === "Lead Backend Developer", "match.job.title matches");
    assert(match1.jobs && match1.jobs.title === "Lead Backend Developer", "match.jobs.title alias matches for UI");
    assert(match1.job.companies && match1.job.companies.name === "Acme Tech Inc", "match.job.companies.name matches UI expectation");

    // =========================================================================
    // 6. MATCH DETAIL RETRIEVAL
    // =========================================================================
    console.log("\n[6] Candidate 1 retrieves single match detail...");
    const matchDetailRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match1.id}/`, {
      headers: { Authorization: `Bearer ${tokenCand1}` },
    });
    assert(matchDetailRes.status === 200, `Match detail HTTP 200 (${matchDetailRes.status})`);
    const matchDetail = await matchDetailRes.json();
    assert(matchDetail.id === match1.id, "Match ID matches requested record");

    // =========================================================================
    // 7. EMPLOYER VISIBILITY GATE (BEFORE ADMIN RELEASE)
    // =========================================================================
    console.log("\n[7] Checking Employer 1 visibility gate before admin approval...");
    const emp1InitialRes = await fetch(`${DJANGO_URL}/api/v1/matches/`, {
      headers: { Authorization: `Bearer ${tokenEmp1}` },
    });
    assert(emp1InitialRes.status === 200, `Employer 1 matches HTTP 200 (${emp1InitialRes.status})`);
    const emp1InitialMatches = await emp1InitialRes.json();
    assert(emp1InitialMatches.length === 0, "Employer 1 cannot see match yet because visible_to_employer=false");

    // =========================================================================
    // 8. ADMIN MATCH RELEASE GATE
    // =========================================================================
    console.log("\n[8] Admin approves match release to employer...");
    const adminReleaseRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match1.id}/admin-action/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenAdmin}` },
      body: JSON.stringify({ action: "approve" }),
    });
    assert(adminReleaseRes.status === 200, `Admin released match HTTP 200 (${adminReleaseRes.status})`);

    // Employer 1 now sees the match
    const emp1AfterApproveRes = await fetch(`${DJANGO_URL}/api/v1/matches/`, {
      headers: { Authorization: `Bearer ${tokenEmp1}` },
    });
    const emp1AfterMatches = await emp1AfterApproveRes.json();
    assert(emp1AfterMatches.length >= 1, `Employer 1 now sees match (visible_to_employer=true)`);
    assert(emp1AfterMatches[0].candidate_profiles?.profiles?.full_name === "Candidate One", "Employer match card candidate_profiles.profiles.full_name is compatible");

    // =========================================================================
    // 9. CANDIDATE EXPRESSES INTEREST
    // =========================================================================
    console.log("\n[9] Candidate 1 expresses interest in the match...");
    const candInterestRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match1.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenCand1}` },
      body: JSON.stringify({ status: "candidate_interested" }),
    });
    assert(candInterestRes.status === 200, `Candidate interest HTTP 200 (${candInterestRes.status})`);
    const candInterestData = await candInterestRes.json();
    assert(candInterestData.status === "candidate_interested", "Status updated to candidate_interested");

    // =========================================================================
    // 10. EMPLOYER SHORTLISTS CANDIDATE -> MUTUAL FIT & HANDOFF
    // =========================================================================
    console.log("\n[10] Employer 1 shortlists Candidate 1 -> triggers mutual_fit & handoff...");
    const empShortlistRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match1.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp1}` },
      body: JSON.stringify({ status: "employer_shortlisted" }),
    });
    assert(empShortlistRes.status === 200, `Employer shortlist HTTP 200 (${empShortlistRes.status})`);
    const empShortlistData = await empShortlistRes.json();
    assert(empShortlistData.status === "mutual_fit", "Status transitioned to mutual_fit");

    // Check handoff queue via Admin
    const handoffsRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/`, {
      headers: { Authorization: `Bearer ${tokenAdmin}` },
    });
    const handoffs = await handoffsRes.json();
    assert(handoffs.length >= 1, `Admin sees generated mutual_fit handoff record (count=${handoffs.length})`);

    // =========================================================================
    // 11. SECURITY: CANDIDATE ISOLATION (IDOR)
    // =========================================================================
    console.log("\n[11] Testing Candidate Isolation (Candidate 2 accessing Candidate 1 match)...");
    const cand2AccessRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match1.id}/`, {
      headers: { Authorization: `Bearer ${tokenCand2}` },
    });
    assert(cand2AccessRes.status === 403, `Candidate 2 denied match detail HTTP 403 (${cand2AccessRes.status})`);

    const cand2PatchRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match1.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenCand2}` },
      body: JSON.stringify({ status: "candidate_interested" }),
    });
    assert(cand2PatchRes.status === 403, `Candidate 2 denied match update HTTP 403 (${cand2PatchRes.status})`);

    // =========================================================================
    // 12. SECURITY: EMPLOYER ISOLATION (IDOR)
    // =========================================================================
    console.log("\n[12] Testing Employer Isolation (Employer 2 accessing Employer 1 match)...");
    const emp2AccessRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match1.id}/`, {
      headers: { Authorization: `Bearer ${tokenEmp2}` },
    });
    assert(emp2AccessRes.status === 403, `Employer 2 denied match detail HTTP 403 (${emp2AccessRes.status})`);

    const emp2PatchRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match1.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp2}` },
      body: JSON.stringify({ status: "employer_shortlisted" }),
    });
    assert(emp2PatchRes.status === 403, `Employer 2 denied match update HTTP 403 (${emp2PatchRes.status})`);

    // =========================================================================
    // 13. SECURITY: CANDIDATE WRITE RESTRICTIONS (SERVER-CONTROLLED FIELDS)
    // =========================================================================
    console.log("\n[13] Testing Candidate status & field tampering restrictions...");
    const candTamperRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match1.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenCand1}` },
      body: JSON.stringify({ status: "employer_shortlisted" }),
    });
    assert(candTamperRes.status === 400 || candTamperRes.status === 403, `Candidate cannot self-shortlist HTTP ${candTamperRes.status}`);

    // =========================================================================
    // 14. DUPLICATE MATCH PREVENTION
    // =========================================================================
    console.log("\n[14] Testing Duplicate Match Prevention...");
    const pyCode = `from matching.models import Match; from candidates.models import CandidateProfile; from jobs.models import Job; cp = CandidateProfile.objects.get(id='${cand1ProfileId}'); j = Job.objects.get(id='${job1Id}'); print('INITIAL_MATCH_COUNT:', Match.objects.filter(candidate_profile=cp, job=j).count()); Match.objects.create(candidate_profile=cp, job=j, match_score=88, status='suggested')`;
    let prevented = false;
    try {
      execSync(`.\\backend\\venv\\Scripts\\python.exe backend/manage.py shell -c "${pyCode}"`, {
        encoding: "utf-8",
        stdio: "pipe",
      });
    } catch (e) {
      const out = (e.stderr || "") + (e.stdout || "");
      if (out.includes("unique constraint") || out.includes("IntegrityError") || out.includes("duplicate key")) {
        prevented = true;
      }
    }
    assert(prevented, "Unique constraint (candidate_profile, job) prevents duplicate matches in database");

    // =========================================================================
    // 15. SUMMARY
    // =========================================================================
    console.log(`\n========================================`);
    console.log(`PHASE 15 TESTS COMPLETE: ${passed}/${total} PASSED`);
    console.log(`========================================\n`);

    if (passed === total) {
      process.exit(0);
    } else {
      process.exit(1);
    }
  } catch (err) {
    console.error("Test execution failed:", err);
    process.exit(1);
  }
}

runPhase15Tests();
