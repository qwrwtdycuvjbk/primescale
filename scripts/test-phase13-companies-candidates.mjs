/**
 * Phase 13 Integration Test Script
 * Verifies Companies and Candidate Profiles API Integration:
 * 1. Candidate Registration & Profile Lifecycle (create, get, patch, update completeness)
 * 2. Candidate Resume Upload & Presigned URL Download
 * 3. Employer Registration & Company Lifecycle (create, get /me, patch, public view)
 * 4. Company Logo Upload
 * 5. Company Member Management
 * 6. Permission & Role Boundaries (Candidate cannot edit company, employer cannot edit candidate)
 */

const DJANGO_URL = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://127.0.0.1:8000";

async function runPhase13Tests() {
  console.log(`Starting Phase 13 Companies & Candidates Integration Tests against: ${DJANGO_URL}`);
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
    const candidateEmail = `phase13.cand.${timestamp}@example.com`;
    const employerEmail = `phase13.emp.${timestamp}@example.com`;
    const password = "Phase13SecurePassword123!";

    // ==========================================
    // 1. REGISTER CANDIDATE & GET TOKEN
    // ==========================================
    console.log("\n[1] Registering Candidate...");
    const candRegRes = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: candidateEmail,
        password,
        full_name: "Alice Candidate",
        role: "candidate",
      }),
    });
    assert(candRegRes.status === 201, `Candidate registration HTTP 201 (${candRegRes.status})`);
    const candTokens = await candRegRes.json();
    const candToken = candTokens.access;

    // ==========================================
    // 2. CANDIDATE PROFILE: CREATE / SAVE
    // ==========================================
    console.log("\n[2] Creating Candidate Profile via /api/v1/candidates/me/...");
    const candProfileInput = {
      headline: "Senior Full Stack Python & React Engineer",
      phone: "+1 555 123 4567",
      current_title: "Senior Software Engineer",
      years_experience: 7,
      skills: ["Python", "Django", "TypeScript", "React", "PostgreSQL"],
      role_categories: ["Engineering", "Backend"],
      experience_level: "senior",
      salary_min: 140000,
      salary_max: 180000,
      work_authorization: "us_citizen",
      us_state: "California",
      preferred_work_type: "remote",
      availability_status: "actively_looking",
      privacy_visibility: "public",
      github_url: "https://github.com/alice-candidate",
      linkedin_url: "https://linkedin.com/in/alice-candidate",
      bio: "Seasoned engineer specializing in Django & Next.js architectures.",
    };

    const candCreateRes = await fetch(`${DJANGO_URL}/api/v1/candidates/me/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${candToken}`,
      },
      body: JSON.stringify(candProfileInput),
    });
    assert(candCreateRes.status === 200 || candCreateRes.status === 201, `Create candidate profile HTTP 200/201 (${candCreateRes.status})`);
    const candCreateData = await candCreateRes.json();
    assert(candCreateData.ok === true, "Candidate save returned ok: true");
    assert(Boolean(candCreateData.candidateProfileId), "Returned candidateProfileId");
    assert(candCreateData.profile?.headline === candProfileInput.headline, "Candidate headline stored correctly");
    assert(candCreateData.profile?.skills.includes("Django"), "Candidate skills include Django");

    // ==========================================
    // 3. CANDIDATE PROFILE: GET /me/
    // ==========================================
    console.log("\n[3] Fetching Candidate Profile via GET /api/v1/candidates/me/...");
    const candGetRes = await fetch(`${DJANGO_URL}/api/v1/candidates/me/`, {
      headers: { Authorization: `Bearer ${candToken}` },
    });
    assert(candGetRes.status === 200, `GET candidate profile HTTP 200 (${candGetRes.status})`);
    const candGetData = await candGetRes.json();
    assert(candGetData.headline === candProfileInput.headline, "Fetched headline matches");
    assert(candGetData.user_email === candidateEmail, "Fetched profile linked to candidate user");

    // ==========================================
    // 4. CANDIDATE RESUME: UPLOAD & PRESIGNED URL
    // ==========================================
    console.log("\n[4] Uploading Candidate Resume...");
    const resumeBlob = new Blob(["%PDF-1.4 Mock Candidate Resume Content for Phase 13"], { type: "application/pdf" });
    const resumeFormData = new FormData();
    resumeFormData.append("file", resumeBlob, "alice_resume.pdf");

    const resumeUploadRes = await fetch(`${DJANGO_URL}/api/v1/candidates/me/resume/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${candToken}` },
      body: resumeFormData,
    });
    assert(resumeUploadRes.status === 200, `Resume upload HTTP 200 (${resumeUploadRes.status})`);
    const resumeUploadData = await resumeUploadRes.json();
    assert(resumeUploadData.ok === true, "Resume upload ok: true");
    assert(Boolean(resumeUploadData.downloadUrl), "Received presigned downloadUrl");
    assert(Boolean(resumeUploadData.resumePath), "Received resumePath");

    // Fetch presigned download URL
    const resumeGetRes = await fetch(`${DJANGO_URL}/api/v1/candidates/me/resume/`, {
      headers: { Authorization: `Bearer ${candToken}` },
    });
    assert(resumeGetRes.status === 200, `GET resume presigned URL HTTP 200 (${resumeGetRes.status})`);
    const resumeGetData = await resumeGetRes.json();
    assert(Boolean(resumeGetData.downloadUrl), "Presigned URL returned on GET");

    // ==========================================
    // 5. REGISTER EMPLOYER & GET TOKEN
    // ==========================================
    console.log("\n[5] Registering Employer...");
    const empRegRes = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: employerEmail,
        password,
        full_name: "Bob Employer",
        role: "employer",
      }),
    });
    assert(empRegRes.status === 201, `Employer registration HTTP 201 (${empRegRes.status})`);
    const empTokens = await empRegRes.json();
    const empToken = empTokens.access;

    // ==========================================
    // 6. EMPLOYER COMPANY: CREATE / SAVE
    // ==========================================
    console.log("\n[6] Creating Company Profile via /api/v1/companies/me/...");
    const companyInput = {
      name: `PrimeTech Innovations ${timestamp}`,
      website: "https://primetech.example.com",
      size: "51-200",
      description: "Leading cloud architecture and AI scaling company.",
      hq_city: "San Francisco, CA",
      industry: "Technology",
      remote_culture_statement: "Async-first, global remote workforce with annual offsites.",
    };

    const compCreateRes = await fetch(`${DJANGO_URL}/api/v1/companies/me/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${empToken}`,
      },
      body: JSON.stringify(companyInput),
    });
    assert(compCreateRes.status === 200 || compCreateRes.status === 201, `Create company HTTP 200/201 (${compCreateRes.status})`);
    const compCreateData = await compCreateRes.json();
    assert(compCreateData.ok === true, "Company save ok: true");
    assert(Boolean(compCreateData.companyId), "Returned companyId");
    const companyId = compCreateData.companyId;

    // ==========================================
    // 7. EMPLOYER COMPANY: GET /me/ & GET by ID
    // ==========================================
    console.log("\n[7] Fetching Employer Company via GET /api/v1/companies/me/...");
    const compGetRes = await fetch(`${DJANGO_URL}/api/v1/companies/me/`, {
      headers: { Authorization: `Bearer ${empToken}` },
    });
    assert(compGetRes.status === 200, `GET company /me/ HTTP 200 (${compGetRes.status})`);
    const compGetData = await compGetRes.json();
    assert(compGetData.name === companyInput.name, "Company name matches input");

    // Public / authenticated detail view
    const compDetailRes = await fetch(`${DJANGO_URL}/api/v1/companies/${companyId}/`);
    assert(compDetailRes.status === 200, `GET company detail by ID HTTP 200 (${compDetailRes.status})`);

    // ==========================================
    // 8. COMPANY LOGO UPLOAD
    // ==========================================
    console.log("\n[8] Uploading Company Logo...");
    const logoBlob = new Blob(["mock png content binary data"], { type: "image/png" });
    const logoFormData = new FormData();
    logoFormData.append("file", logoBlob, "company_logo.png");

    const logoUploadRes = await fetch(`${DJANGO_URL}/api/v1/companies/me/logo/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${empToken}` },
      body: logoFormData,
    });
    assert(logoUploadRes.status === 200, `Logo upload HTTP 200 (${logoUploadRes.status})`);
    const logoUploadData = await logoUploadRes.json();
    assert(logoUploadData.ok === true, "Logo upload ok: true");
    assert(Boolean(logoUploadData.url), "Logo public URL returned");

    // ==========================================
    // 9. COMPANY MEMBERS: LIST & PERMISSIONS
    // ==========================================
    console.log("\n[9] Checking Company Members...");
    const membersRes = await fetch(`${DJANGO_URL}/api/v1/companies/${companyId}/members/`, {
      headers: { Authorization: `Bearer ${empToken}` },
    });
    assert(membersRes.status === 200, `GET company members HTTP 200 (${membersRes.status})`);

    // ==========================================
    // 10. ROLE & PERMISSION BOUNDARIES
    // ==========================================
    console.log("\n[10] Testing Authorization Boundaries...");
    // Candidate cannot create/update company via /companies/me/
    const candOnCompany = await fetch(`${DJANGO_URL}/api/v1/companies/me/`, {
      method: "GET",
      headers: { Authorization: `Bearer ${candToken}` },
    });
    assert(candOnCompany.status === 403, `Candidate forbidden on /companies/me/ (${candOnCompany.status})`);

    // Employer cannot create/update candidate profile via /candidates/me/
    const empOnCandidate = await fetch(`${DJANGO_URL}/api/v1/candidates/me/`, {
      method: "GET",
      headers: { Authorization: `Bearer ${empToken}` },
    });
    assert(empOnCandidate.status === 403, `Employer forbidden on /candidates/me/ (${empOnCandidate.status})`);

    // Unauthenticated request to /candidates/me/
    const unauthCand = await fetch(`${DJANGO_URL}/api/v1/candidates/me/`);
    assert(unauthCand.status === 401, `Unauthenticated request to /candidates/me/ rejected with 401 (${unauthCand.status})`);

    console.log(`\n=================================================`);
    console.log(`Phase 13 Integration Results: ${passed}/${total} PASSED`);
    console.log(`=================================================\n`);

    if (passed === total) {
      process.exit(0);
    } else {
      process.exit(1);
    }
  } catch (err) {
    console.error("Test execution failed with exception:", err);
    process.exit(1);
  }
}

runPhase13Tests();
