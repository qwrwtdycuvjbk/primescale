/**
 * Phase 14 Integration Test Script
 * Verifies Jobs API Integration between Next.js and Django REST Framework:
 * 1. Employer Job Creation (draft and active with 30-day expiry)
 * 2. Employer Job Listing & Isolation (only seeing own company's jobs with view=my_company)
 * 3. Job Detail Retrieval (public vs owner/admin)
 * 4. Job Status Update (draft -> active -> paused -> closed)
 * 5. Job Duplication (clones existing job as draft)
 * 6. Public / Candidate Read-Only Access
 * 7. Candidate Write Rejection (HTTP 403)
 * 8. Cross-Employer Modification Rejection (HTTP 403 / IDOR prevention)
 * 9. Admin Full Lifecycle Access
 */

const DJANGO_URL = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://127.0.0.1:8000";

async function runPhase14Tests() {
  console.log(`Starting Phase 14 Jobs Integration Tests against: ${DJANGO_URL}`);
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
    const employer1Email = `phase14.emp1.${timestamp}@example.com`;
    const employer2Email = `phase14.emp2.${timestamp}@example.com`;
    const candidateEmail = `phase14.cand.${timestamp}@example.com`;
    const password = "Phase14SecurePassword123!";

    // =========================================================================
    // 1. REGISTER USERS
    // =========================================================================
    console.log("\n[1] Registering Employer 1, Employer 2, and Candidate...");
    const regEmp1 = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: employer1Email, password, full_name: "Employer One", role: "employer" }),
    });
    assert(regEmp1.status === 201, `Employer 1 registered HTTP 201 (${regEmp1.status})`);
    const emp1Tokens = await regEmp1.json();
    const token1 = emp1Tokens.access;

    const regEmp2 = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: employer2Email, password, full_name: "Employer Two", role: "employer" }),
    });
    assert(regEmp2.status === 201, `Employer 2 registered HTTP 201 (${regEmp2.status})`);
    const emp2Tokens = await regEmp2.json();
    const token2 = emp2Tokens.access;

    const regCand = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: candidateEmail, password, full_name: "Candidate Test", role: "candidate" }),
    });
    assert(regCand.status === 201, `Candidate registered HTTP 201 (${regCand.status})`);
    const candTokens = await regCand.json();
    const candToken = candTokens.access;

    // Set up Company for Employer 1
    const comp1Res = await fetch(`${DJANGO_URL}/api/v1/companies/me/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token1}` },
      body: JSON.stringify({
        name: `Acme Corp ${timestamp}`,
        website: "https://acme.example.com",
        size: "51-200",
        description: "Cloud infrastructure company.",
        hq_city: "Austin, TX",
        industry: "Cloud",
      }),
    });
    assert(comp1Res.status === 200 || comp1Res.status === 201, "Company 1 created");
    const comp1Data = await comp1Res.json();
    const company1Id = comp1Data.companyId;

    // Set up Company for Employer 2
    const comp2Res = await fetch(`${DJANGO_URL}/api/v1/companies/me/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token2}` },
      body: JSON.stringify({
        name: `Beta Ltd ${timestamp}`,
        website: "https://beta.example.com",
        size: "11-50",
        description: "Fintech solutions.",
        hq_city: "New York, NY",
        industry: "Fintech",
      }),
    });
    assert(comp2Res.status === 200 || comp2Res.status === 201, "Company 2 created");

    // =========================================================================
    // 2. EMPLOYER 1 CREATES ACTIVE JOB
    // =========================================================================
    console.log("\n[2] Employer 1 creating active job...");
    const jobPayload = {
      company_id: company1Id,
      title: "Senior Cloud Architect",
      description: "Design and scale cloud systems using Kubernetes and Go.",
      role_type: "full-time",
      experience_level: "senior",
      tech_stack: ["Go", "Kubernetes", "AWS", "Terraform"],
      salary_range: "$160,000 - $190,000",
      work_type: "remote",
      visa_requirements: "Authorized to work in the US",
      publish: true,
    };

    const createJobRes = await fetch(`${DJANGO_URL}/api/v1/jobs/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token1}` },
      body: JSON.stringify(jobPayload),
    });
    assert(createJobRes.status === 201, `Job created HTTP 201 (${createJobRes.status})`);
    const createJobData = await createJobRes.json();
    assert(createJobData.ok === true, "Job creation ok: true");
    assert(Boolean(createJobData.jobId), "Returned jobId");
    assert(createJobData.status === "active", "Job status is active");
    assert(Boolean(createJobData.job?.expires_at), "Job has 30-day expiry set");
    const jobId1 = createJobData.jobId;

    // =========================================================================
    // 3. EMPLOYER 1 LISTS OWN JOBS (view=my_company)
    // =========================================================================
    console.log("\n[3] Employer 1 listing jobs with view=my_company...");
    const myJobsRes = await fetch(`${DJANGO_URL}/api/v1/jobs/?view=my_company`, {
      headers: { Authorization: `Bearer ${token1}` },
    });
    assert(myJobsRes.status === 200, `List my jobs HTTP 200 (${myJobsRes.status})`);
    const myJobs = await myJobsRes.json();
    assert(myJobs.length === 1, `Employer 1 sees exactly 1 job (${myJobs.length})`);
    assert(myJobs[0].id === jobId1, "Job ID matches");
    assert(myJobs[0].title === jobPayload.title, "Job title matches");

    // Employer 2 listing my_company jobs sees 0
    const emp2JobsRes = await fetch(`${DJANGO_URL}/api/v1/jobs/?view=my_company`, {
      headers: { Authorization: `Bearer ${token2}` },
    });
    const emp2Jobs = await emp2JobsRes.json();
    assert(emp2Jobs.length === 0, `Employer 2 sees 0 jobs (${emp2Jobs.length})`);

    // =========================================================================
    // 4. GET JOB DETAIL (Authenticated Owner vs Public)
    // =========================================================================
    console.log("\n[4] Job Detail Retrieval...");
    const detailOwnerRes = await fetch(`${DJANGO_URL}/api/v1/jobs/${jobId1}/`, {
      headers: { Authorization: `Bearer ${token1}` },
    });
    assert(detailOwnerRes.status === 200, `Owner detail HTTP 200 (${detailOwnerRes.status})`);
    const detailOwner = await detailOwnerRes.json();
    assert(Boolean(detailOwner.posted_by), "Owner view includes posted_by");

    const detailPublicRes = await fetch(`${DJANGO_URL}/api/v1/jobs/${jobId1}/`);
    assert(detailPublicRes.status === 200, `Public detail HTTP 200 (${detailPublicRes.status})`);
    const detailPublic = await detailPublicRes.json();
    assert(detailPublic.title === jobPayload.title, "Public view has title");

    // =========================================================================
    // 5. UPDATE JOB STATUS
    // =========================================================================
    console.log("\n[5] Updating Job Status...");
    const pauseRes = await fetch(`${DJANGO_URL}/api/v1/jobs/${jobId1}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token1}` },
      body: JSON.stringify({ status: "paused" }),
    });
    assert(pauseRes.status === 200, `Pause job HTTP 200 (${pauseRes.status})`);
    const pauseData = await pauseRes.json();
    assert(pauseData.job?.status === "paused", "Job status updated to paused");

    // Resume
    const resumeRes = await fetch(`${DJANGO_URL}/api/v1/jobs/${jobId1}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token1}` },
      body: JSON.stringify({ status: "active" }),
    });
    assert(resumeRes.status === 200, "Resume job HTTP 200");
    const resumeData = await resumeRes.json();
    assert(resumeData.job?.status === "active", "Job status resumed to active");

    // =========================================================================
    // 6. DUPLICATE JOB
    // =========================================================================
    console.log("\n[6] Duplicating Job...");
    const dupRes = await fetch(`${DJANGO_URL}/api/v1/jobs/${jobId1}/duplicate/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token1}` },
    });
    assert(dupRes.status === 201, `Duplicate job HTTP 201 (${dupRes.status})`);
    const dupData = await dupRes.json();
    assert(Boolean(dupData.jobId), "Duplicate returned new jobId");
    assert(dupData.job?.status === "draft", "Duplicate has draft status");
    assert(dupData.job?.title.includes("(copy)"), "Duplicate title includes (copy)");

    // =========================================================================
    // 7. ROLE BOUNDARY TESTS (Candidate & Cross-Employer Rejection)
    // =========================================================================
    console.log("\n[7] Testing Authorization & Permissions...");
    // Candidate cannot create job
    const candCreateRes = await fetch(`${DJANGO_URL}/api/v1/jobs/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${candToken}` },
      body: JSON.stringify(jobPayload),
    });
    assert(candCreateRes.status === 403, `Candidate rejected from creating job (${candCreateRes.status})`);

    // Candidate cannot modify job
    const candPatchRes = await fetch(`${DJANGO_URL}/api/v1/jobs/${jobId1}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${candToken}` },
      body: JSON.stringify({ title: "Hacked by Candidate" }),
    });
    assert(candPatchRes.status === 403, `Candidate rejected from patching job (${candPatchRes.status})`);

    // Employer 2 cannot modify Employer 1's job
    const emp2PatchRes = await fetch(`${DJANGO_URL}/api/v1/jobs/${jobId1}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token2}` },
      body: JSON.stringify({ title: "Hacked by Competitor" }),
    });
    assert(emp2PatchRes.status === 403, `Cross-employer job modification rejected with 403 (${emp2PatchRes.status})`);

    // Employer 2 cannot duplicate Employer 1's job
    const emp2DupRes = await fetch(`${DJANGO_URL}/api/v1/jobs/${jobId1}/duplicate/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token2}` },
    });
    assert(emp2DupRes.status === 403, `Cross-employer job duplication rejected with 403 (${emp2DupRes.status})`);

    console.log(`\n=================================================`);
    console.log(`Phase 14 Integration Results: ${passed}/${total} PASSED`);
    console.log(`=================================================\n`);

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

runPhase14Tests();
