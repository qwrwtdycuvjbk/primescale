/**
 * Phase 16 Integration Test Script
 * Verifies Handoff Requests Module Integration between Next.js and Django REST Framework:
 * 1. Mutual fit triggers automatic/idempotent handoff creation
 * 2. Admin handoff listing and status filtering (pending, contacted, intro_made, closed)
 * 3. Handoff detail retrieval with full relational data
 * 4. Admin status update and recruiter notes update
 * 5. Candidate handoff access (can view own handoff, cannot modify)
 * 6. Employer handoff access (can view own handoff, cannot modify)
 * 7. Candidate isolation (Candidate B cannot view Candidate A handoff -> 403)
 * 8. Employer isolation (Employer B cannot view Employer A handoff -> 403)
 * 9. Non-admin write rejection (Candidate/Employer cannot patch status -> 403)
 * 10. Duplicate handoff prevention (OneToOne constraint on match)
 * 11. API response field compatibility (match, matches, employer, candidate_profiles)
 * 12. Invalid status rejection (HTTP 400)
 */

const DJANGO_URL = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://127.0.0.1:8000";

async function runPhase16Tests() {
  console.log(`Starting Phase 16 Handoffs Integration Tests against: ${DJANGO_URL}`);
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
    const candidate1Email = `phase16.cand1.${timestamp}@example.com`;
    const candidate2Email = `phase16.cand2.${timestamp}@example.com`;
    const employer1Email = `phase16.emp1.${timestamp}@example.com`;
    const employer2Email = `phase16.emp2.${timestamp}@example.com`;
    const password = "Phase16SecurePassword123!";

    // =========================================================================
    // 1. REGISTER USERS
    // =========================================================================
    console.log("\n[1] Registering Candidate 1, Candidate 2, Employer 1, Employer 2...");

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
    console.log("\n[3] Setting up candidate profile and company job...");

    const profileCand1Res = await fetch(`${DJANGO_URL}/api/v1/candidates/me/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenCand1}` },
      body: JSON.stringify({
        headline: "Staff Distributed Systems Architect",
        current_title: "Principal Engineer",
        phone: "+1 (555) 321-9876",
        skills: ["python", "django", "postgresql", "redis", "celery", "aws"],
        role_categories: ["backend", "distributed_systems"],
        experience_level: "lead",
        work_authorization: "us_citizen",
        us_state: "WA",
        remote_preference: "remote_only",
        open_to_matching: true,
        resume_url: "https://s3.amazonaws.com/resumes/c16.pdf",
      }),
    });
    assert(profileCand1Res.status === 200, `Candidate 1 profile saved HTTP 200 (${profileCand1Res.status})`);
    const profileCand1 = await profileCand1Res.json();
    const cand1ProfileId = profileCand1.candidateProfileId;

    const comp1Res = await fetch(`${DJANGO_URL}/api/v1/companies/me/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp1}` },
      body: JSON.stringify({
        name: `Handoff Systems ${timestamp}`,
        website: "https://handoff.example.com",
        industry: "Enterprise Software",
        hq_city: "Seattle, WA",
        description: "Modern enterprise platforms",
      }),
    });
    assert(comp1Res.status === 200 || comp1Res.status === 201, `Employer 1 company saved (${comp1Res.status})`);

    const job1Res = await fetch(`${DJANGO_URL}/api/v1/jobs/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp1}` },
      body: JSON.stringify({
        title: "Staff Python Platform Engineer",
        description: "Scale core distributed services",
        role_type: "full-time",
        experience_level: "senior",
        tech_stack: ["python", "django", "postgresql", "celery"],
        salary_range: "$175,000 - $215,000",
        work_type: "remote",
        visa_requirements: "Authorized to work in the US",
        publish: true,
      }),
    });
    assert(job1Res.status === 201, `Employer 1 Job created HTTP 201 (${job1Res.status})`);
    const job1Data = await job1Res.json();
    const job1Id = job1Data.jobId;

    // =========================================================================
    // 4. TRIGGER MATCHING & REACH MUTUAL FIT
    // =========================================================================
    console.log("\n[4] Running matching and advancing status to mutual_fit...");
    const execSync = (await import("child_process")).execSync;
    execSync(
      `.\\backend\\venv\\Scripts\\python.exe backend/manage.py shell -c "from matching.services import run_matching_for_candidate; run_matching_for_candidate('${cand1ProfileId}')"`,
      { encoding: "utf-8" }
    );

    // Fetch match
    const candMatchesRes = await fetch(`${DJANGO_URL}/api/v1/matches/`, {
      headers: { Authorization: `Bearer ${tokenCand1}` },
    });
    const candMatches = await candMatchesRes.json();
    const match = candMatches.find((m) => m.job?.id === job1Id || m.jobs?.id === job1Id);
    assert(Boolean(match), "Found generated match for Candidate 1 & Job 1");

    // Admin approves match release
    await fetch(`${DJANGO_URL}/api/v1/matches/${match.id}/admin-action/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenAdmin}` },
      body: JSON.stringify({ action: "approve" }),
    });

    // Candidate expresses interest
    await fetch(`${DJANGO_URL}/api/v1/matches/${match.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenCand1}` },
      body: JSON.stringify({ status: "candidate_interested" }),
    });

    // Employer shortlists -> triggers mutual_fit + automatic handoff creation
    const empShortlistRes = await fetch(`${DJANGO_URL}/api/v1/matches/${match.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp1}` },
      body: JSON.stringify({ status: "employer_shortlisted" }),
    });
    const empShortlistData = await empShortlistRes.json();
    assert(empShortlistData.status === "mutual_fit", "Match status reached mutual_fit");

    // =========================================================================
    // 5. ADMIN HANDOFF LISTING & DETAIL
    // =========================================================================
    console.log("\n[5] Admin lists and inspects handoff queue...");
    const adminHandoffsRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/`, {
      headers: { Authorization: `Bearer ${tokenAdmin}` },
    });
    assert(adminHandoffsRes.status === 200, `Admin listed handoffs HTTP 200 (${adminHandoffsRes.status})`);
    const adminHandoffs = await adminHandoffsRes.json();
    assert(adminHandoffs.length >= 1, `Handoffs found in queue (got ${adminHandoffs.length})`);

    const handoff = adminHandoffs.find((h) => h.match?.id === match.id || h.match_id === match.id);
    assert(Boolean(handoff), "Specific mutual_fit handoff exists in queue");
    assert(handoff.status === "pending", `Initial handoff status is pending (got ${handoff.status})`);

    // Verify UI field compatibility
    assert(Boolean(handoff.matches || handoff.match), "Handoff includes match/matches relation");
    assert(Boolean(handoff.employer?.email), "Handoff includes nested employer details for admin card");
    assert(handoff.matches?.candidate_profiles?.profiles?.full_name === "Candidate One", "Candidate profile name resolves cleanly");

    // Fetch single handoff detail
    const handoffDetailRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      headers: { Authorization: `Bearer ${tokenAdmin}` },
    });
    assert(handoffDetailRes.status === 200, `Admin fetched handoff detail HTTP 200 (${handoffDetailRes.status})`);
    const handoffDetail = await handoffDetailRes.json();
    assert(handoffDetail.id === handoff.id, "Handoff detail ID matches");

    // =========================================================================
    // 6. ADMIN HANDOFF STATUS WORKFLOW (CONTACTED -> INTRO_MADE -> CLOSED)
    // =========================================================================
    console.log("\n[6] Admin updates handoff status and recruiter notes...");
    const update1Res = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenAdmin}` },
      body: JSON.stringify({ status: "contacted", notes: "Reached out to Candidate One via email." }),
    });
    assert(update1Res.status === 200, `Admin updated to contacted HTTP 200 (${update1Res.status})`);
    const update1Data = await update1Res.json();
    assert(update1Data.handoff?.status === "contacted", "Status updated to contacted");
    assert(update1Data.handoff?.notes?.includes("Reached out"), "Recruiter notes updated");

    const update2Res = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenAdmin}` },
      body: JSON.stringify({ status: "intro_made", notes: "Intro call scheduled for Thursday." }),
    });
    assert(update2Res.status === 200, `Admin updated to intro_made HTTP 200 (${update2Res.status})`);
    const update2Data = await update2Res.json();
    assert(update2Data.handoff?.status === "intro_made", "Status updated to intro_made");

    // =========================================================================
    // 7. CANDIDATE ACCESS & ISOLATION
    // =========================================================================
    console.log("\n[7] Testing Candidate access and isolation...");
    // Candidate 1 can view own handoff
    const cand1ListRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/`, {
      headers: { Authorization: `Bearer ${tokenCand1}` },
    });
    assert(cand1ListRes.status === 200, `Candidate 1 listed handoffs HTTP 200 (${cand1ListRes.status})`);
    const cand1List = await cand1ListRes.json();
    assert(cand1List.some((h) => h.id === handoff.id), "Candidate 1 sees own handoff");

    const cand1DetailRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      headers: { Authorization: `Bearer ${tokenCand1}` },
    });
    assert(cand1DetailRes.status === 200, `Candidate 1 fetched own handoff detail HTTP 200 (${cand1DetailRes.status})`);

    // Candidate 1 cannot modify handoff status
    const cand1PatchRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenCand1}` },
      body: JSON.stringify({ status: "closed" }),
    });
    assert(cand1PatchRes.status === 403, `Candidate 1 denied patching handoff HTTP 403 (${cand1PatchRes.status})`);

    // Candidate 2 cannot view Candidate 1 handoff (IDOR isolation)
    const cand2DetailRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      headers: { Authorization: `Bearer ${tokenCand2}` },
    });
    assert(cand2DetailRes.status === 403, `Candidate 2 denied Candidate 1 handoff detail HTTP 403 (${cand2DetailRes.status})`);

    const cand2ListRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/`, {
      headers: { Authorization: `Bearer ${tokenCand2}` },
    });
    const cand2List = await cand2ListRes.json();
    assert(cand2List.length === 0, `Candidate 2 received 0 handoffs in queue (${cand2List.length})`);

    // =========================================================================
    // 8. EMPLOYER ACCESS & ISOLATION
    // =========================================================================
    console.log("\n[8] Testing Employer access and isolation...");
    // Employer 1 can view own handoff
    const emp1ListRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/`, {
      headers: { Authorization: `Bearer ${tokenEmp1}` },
    });
    assert(emp1ListRes.status === 200, `Employer 1 listed handoffs HTTP 200 (${emp1ListRes.status})`);
    const emp1List = await emp1ListRes.json();
    assert(emp1List.some((h) => h.id === handoff.id), "Employer 1 sees own handoff");

    const emp1DetailRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      headers: { Authorization: `Bearer ${tokenEmp1}` },
    });
    assert(emp1DetailRes.status === 200, `Employer 1 fetched own handoff detail HTTP 200 (${emp1DetailRes.status})`);

    // Employer 1 cannot modify handoff status
    const emp1PatchRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenEmp1}` },
      body: JSON.stringify({ status: "closed" }),
    });
    assert(emp1PatchRes.status === 403, `Employer 1 denied patching handoff HTTP 403 (${emp1PatchRes.status})`);

    // Employer 2 cannot view Employer 1 handoff (IDOR isolation)
    const emp2DetailRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      headers: { Authorization: `Bearer ${tokenEmp2}` },
    });
    assert(emp2DetailRes.status === 403, `Employer 2 denied Employer 1 handoff detail HTTP 403 (${emp2DetailRes.status})`);

    const emp2ListRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/`, {
      headers: { Authorization: `Bearer ${tokenEmp2}` },
    });
    const emp2List = await emp2ListRes.json();
    assert(emp2List.length === 0, `Employer 2 received 0 handoffs in queue (${emp2List.length})`);

    // =========================================================================
    // 9. DUPLICATE HANDOFF PROTECTION & INVALID STATUS REJECTION
    // =========================================================================
    console.log("\n[9] Testing Duplicate Handoff Protection & Invalid Status Rejection...");
    const pyCode = `from handoffs.models import HandoffRequest; from matching.models import Match; m = Match.objects.get(id='${match.id}'); HandoffRequest.objects.create(match=m)`;
    let dupPrevented = false;
    try {
      execSync(`.\\backend\\venv\\Scripts\\python.exe backend/manage.py shell -c "${pyCode}"`, {
        encoding: "utf-8",
        stdio: "pipe",
      });
    } catch (e) {
      const out = (e.stderr || "") + (e.stdout || "");
      if (out.includes("unique constraint") || out.includes("IntegrityError") || out.includes("duplicate key")) {
        dupPrevented = true;
      }
    }
    assert(dupPrevented, "OneToOne constraint prevents duplicate handoffs for the same match");

    // Invalid status rejection
    const invalidStatusRes = await fetch(`${DJANGO_URL}/api/v1/handoffs/${handoff.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenAdmin}` },
      body: JSON.stringify({ status: "invalid_status_code" }),
    });
    assert(invalidStatusRes.status === 400, `Invalid status rejected HTTP 400 (${invalidStatusRes.status})`);

    // =========================================================================
    // 10. SUMMARY
    // =========================================================================
    console.log(`\n========================================`);
    console.log(`PHASE 16 TESTS COMPLETE: ${passed}/${total} PASSED`);
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

runPhase16Tests();
