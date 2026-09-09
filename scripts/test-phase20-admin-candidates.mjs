/**
 * Phase 20 Integration Test Suite:
 * Admin Candidates & Bulk Import Migration.
 *
 * Covers requirements from Section 16:
 * 1. Admin login
 * 2. Candidate login
 * 3. Employer login
 * 4. Admin GET candidates -> 200
 * 5. Candidate GET candidates -> 403
 * 6. Employer GET candidates -> 403
 * 7. Unauthenticated GET candidates -> 401
 * 8. Search filtering
 * 9. Availability filtering
 * 10. Experience filtering
 * 11. Completeness filtering
 * 12. Work authorization filtering
 * 13. Source filtering
 * 14. Pagination
 * 15. Admin creates candidate -> 201
 * 16. Candidate cannot create candidate -> 403
 * 17. Employer cannot create candidate -> 403
 * 18. Duplicate email rejected -> 400
 * 19. Email normalization verified
 * 20. Admin receives presigned resume URL (or 404 for missing resume handled correctly)
 * 21. Candidate cannot access admin resume endpoint -> 403
 * 22. Employer cannot access admin resume endpoint -> 403
 * 23. Invalid candidate ID handled correctly (404)
 * 24. Valid CSV import
 * 25. Valid JSON parsed import
 * 26. Duplicate email handling in bulk import
 * 27. Invalid email handling in bulk import
 * 28. Missing required field handling
 * 29. Row-level errors returned
 * 30. Transaction / partial failure behavior
 * 31. Resume stored through Django S3 backend (or verified URL)
 * 32. Resume access private via presigned URL
 * 33. Presigned URL generated successfully
 * 34. Admin jobs page uses Django API
 * 35. Company selector uses Django API
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
  console.log(`Starting Phase 20 Admin Candidates & Bulk Import Tests against: ${BASE_URL}\n`);
  const ts = Date.now();

  const adminEmail = `admin.${ts}@example.com`;
  const candEmail = `cand.${ts}@example.com`;
  const empEmail = `emp.${ts}@example.com`;
  const password = "Phase20Password!123";

  // Setup accounts
  console.log("[Authentication Setup]");
  // 1. Admin Login
  const aLogin = await fetch(`${BASE_URL}/api/v1/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@peopleremotely.com", password: "AdminPassword123!" }),
  });
  const aData = await aLogin.json();
  assert(aLogin.status === 200, `1. Admin login HTTP 200 (${aLogin.status})`);
  const adminToken = aData.access;

  // 2. Candidate
  const cReg = await fetch(`${BASE_URL}/api/v1/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: candEmail, password, role: "candidate", full_name: "Phase 20 Candidate" }),
  });
  const cData = await cReg.json();
  assert(cReg.status === 201, `2. Candidate login/registration HTTP 201 (${cReg.status})`);
  const candToken = cData.access;

  // 3. Employer
  const eReg = await fetch(`${BASE_URL}/api/v1/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: empEmail, password, role: "employer", full_name: "Phase 20 Employer" }),
  });
  const eData = await eReg.json();
  assert(eReg.status === 201, `3. Employer login/registration HTTP 201 (${eReg.status})`);
  const empToken = eData.access;

  // Candidate Registry
  console.log("\n[Candidate Registry & RBAC]");
  // 4. Admin GET candidates -> 200
  const adminList = await fetch(`${BASE_URL}/api/v1/admin/candidates/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  const adminListData = await adminList.json();
  assert(adminList.status === 200, `4. Admin GET candidates HTTP 200 (${adminList.status})`);
  assert(Array.isArray(adminListData.results), "4b. Admin candidate results returned as array");
  assert(typeof adminListData.totalCount === "number", "4c. Metrics summary included (totalCount)");

  // 5. Candidate GET candidates -> 403
  const candList = await fetch(`${BASE_URL}/api/v1/admin/candidates/`, {
    headers: { Authorization: `Bearer ${candToken}` },
  });
  assert(candList.status === 403, `5. Candidate GET candidates HTTP 403 (${candList.status})`);

  // 6. Employer GET candidates -> 403
  const empList = await fetch(`${BASE_URL}/api/v1/admin/candidates/`, {
    headers: { Authorization: `Bearer ${empToken}` },
  });
  assert(empList.status === 403, `6. Employer GET candidates HTTP 403 (${empList.status})`);

  // 7. Unauthenticated -> 401
  const unauthList = await fetch(`${BASE_URL}/api/v1/admin/candidates/`);
  assert(unauthList.status === 401, `7. Unauthenticated GET candidates HTTP 401 (${unauthList.status})`);

  // 8. Search
  const searchRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/?q=Phase`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  const searchData = await searchRes.json();
  assert(searchRes.status === 200 && searchData.results.length > 0, `8. Search query q=Phase returns matches (${searchData.results.length})`);

  // 9. Availability filtering
  const availRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/?availability=immediate`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  assert(availRes.status === 200, `9. Availability filter HTTP 200`);

  // 10. Experience filtering
  const expRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/?experience=senior`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  assert(expRes.status === 200, `10. Experience filter HTTP 200`);

  // 11. Completeness filtering
  const compRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/?complete=false`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  assert(compRes.status === 200, `11. Completeness filter HTTP 200`);

  // 12. Work authorization filtering
  const authRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/?work_auth=us_citizen`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  assert(authRes.status === 200, `12. Work authorization filter HTTP 200`);

  // 13. Source filtering
  const srcRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/?source=manual_admin`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  assert(srcRes.status === 200, `13. Source filter HTTP 200`);

  // 14. Pagination
  const pageRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/?limit=1&offset=0`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  const pageData = await pageRes.json();
  assert(pageRes.status === 200 && pageData.results.length <= 1, `14. Pagination limit=1 HTTP 200 with <=1 item`);

  // Candidate Creation
  console.log("\n[Candidate Creation & Duplicate Protection]");
  const newCandidateEmail = `created.cand.${ts}@example.com`;
  // 15. Admin creates candidate -> 201
  const createRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${adminToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: newCandidateEmail,
      full_name: "Created Candidate Admin",
      phone: "+1234567890",
      skills: ["React", "Python", "PostgreSQL"],
      experience_level: "senior",
      years_experience: 6,
      availability: "immediate",
      work_authorization: "us_citizen",
    }),
  });
  const createData = await createRes.json();
  assert(createRes.status === 201, `15. Admin creates candidate HTTP 201 (${createRes.status})`);
  assert(Boolean(createData.id), "15b. Created candidate has UUID id");
  const createdCandidateId = createData.id;

  // 16. Candidate cannot create candidate -> 403
  const candCreate = await fetch(`${BASE_URL}/api/v1/admin/candidates/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${candToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email: `cand.try.${ts}@example.com`, full_name: "Unauthorized Candidate" }),
  });
  assert(candCreate.status === 403, `16. Candidate cannot create candidate HTTP 403 (${candCreate.status})`);

  // 17. Employer cannot create candidate -> 403
  const empCreate = await fetch(`${BASE_URL}/api/v1/admin/candidates/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${empToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email: `emp.try.${ts}@example.com`, full_name: "Unauthorized Employer" }),
  });
  assert(empCreate.status === 403, `17. Employer cannot create candidate HTTP 403 (${empCreate.status})`);

  // 18. Duplicate email rejected
  const dupCreate = await fetch(`${BASE_URL}/api/v1/admin/candidates/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${adminToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: newCandidateEmail.toUpperCase(), // Test case insensitivity / normalization
      full_name: "Duplicate Candidate",
    }),
  });
  assert(dupCreate.status === 400, `18. Duplicate email rejected HTTP 400 (${dupCreate.status})`);

  // 19. Email normalization verified
  const normList = await fetch(`${BASE_URL}/api/v1/admin/candidates/?q=${newCandidateEmail}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  const normData = await normList.json();
  assert(
    normData.results.some((c) => c.profiles?.email === newCandidateEmail.toLowerCase()),
    "19. Email normalization verified in candidate profile"
  );

  // Resume Endpoints
  console.log("\n[Resume Storage & Presigned URLs]");
  // 20. Admin receives presigned resume URL (or 404 for candidate with no resume yet)
  const resumeRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/${createdCandidateId}/resume/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  // Candidate has no resume yet -> 404
  assert(resumeRes.status === 404, `20. Candidate with no resume correctly returns HTTP 404 (${resumeRes.status})`);

  // 21. Candidate cannot access admin resume endpoint -> 403
  const candResume = await fetch(`${BASE_URL}/api/v1/admin/candidates/${createdCandidateId}/resume/`, {
    headers: { Authorization: `Bearer ${candToken}` },
  });
  assert(candResume.status === 403, `21. Candidate cannot access admin resume endpoint HTTP 403 (${candResume.status})`);

  // 22. Employer cannot access admin resume endpoint -> 403
  const empResume = await fetch(`${BASE_URL}/api/v1/admin/candidates/${createdCandidateId}/resume/`, {
    headers: { Authorization: `Bearer ${empToken}` },
  });
  assert(empResume.status === 403, `22. Employer cannot access admin resume endpoint HTTP 403 (${empResume.status})`);

  // 23. Invalid candidate ID handled correctly (404)
  const invalidResume = await fetch(`${BASE_URL}/api/v1/admin/candidates/00000000-0000-0000-0000-000000000000/resume/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  assert(invalidResume.status === 404, `23. Invalid candidate ID returns HTTP 404 (${invalidResume.status})`);

  // Bulk Import
  console.log("\n[Bulk Candidate Import]");
  const bulkCandidateEmail1 = `bulk1.${ts}@example.com`;
  const bulkCandidateEmail2 = `bulk2.${ts}@example.com`;

  // 24. Valid CSV import
  const csvContent = `full_name,email,phone,skills,experience_level,years_experience,availability,work_authorization
Alice Bulk,${bulkCandidateEmail1},+111111,"React,TypeScript",mid,3,immediate,us_citizen
Bob Bulk,${bulkCandidateEmail2},+222222,"Python,Django",senior,5,2_weeks,green_card`;

  const boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
  const body = `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="candidates.csv"\r\nContent-Type: text/csv\r\n\r\n${csvContent}\r\n--${boundary}--\r\n`;

  const csvImportRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/import/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${adminToken}`,
      "Content-Type": `multipart/form-data; boundary=${boundary}`,
    },
    body: body,
  });
  const csvImportData = await csvImportRes.json();
  assert(csvImportRes.status === 200, `24. Valid CSV import HTTP 200 (${csvImportRes.status})`);
  assert(csvImportData.created === 2, `24b. Correctly created 2 candidates from CSV (created=${csvImportData.created})`);

  // 25. Valid JSON parsed import
  const jsonBatchEmail = `jsonbatch.${ts}@example.com`;
  const jsonImportRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/import/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${adminToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      rows: [
        {
          full_name: "Charlie Batch",
          email: jsonBatchEmail,
          skills: ["Go", "Docker"],
          experience_level: "lead",
        },
      ],
    }),
  });
  const jsonImportData = await jsonImportRes.json();
  assert(jsonImportRes.status === 200, `25. Valid JSON parsed import HTTP 200 (${jsonImportRes.status})`);
  assert(jsonImportData.created === 1, `25b. Created 1 candidate from JSON batch`);

  // 26. Duplicate email handling in bulk import
  // 27. Invalid email handling
  // 28. Missing required field handling
  // 29. Row-level errors returned
  // 30. Transaction / partial failure behavior
  const mixedBatchRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/import/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${adminToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      rows: [
        {
          full_name: "Duplicate Candidate",
          email: bulkCandidateEmail1, // already exists
        },
        {
          full_name: "Bad Email Candidate",
          email: "not-an-email",
        },
        {
          email: `valid.${ts}@example.com`, // missing full_name
        },
        {
          full_name: "Good Candidate",
          email: `good.${ts}@example.com`,
          skills: ["Django"],
        },
      ],
    }),
  });
  const mixedBatchData = await mixedBatchRes.json();
  assert(mixedBatchRes.status === 200, `26-30. Mixed batch import HTTP 200 (${mixedBatchRes.status})`);
  assert(mixedBatchData.created === 1, `26b. Created 1 valid candidate in mixed batch`);
  assert(mixedBatchData.failed === 3, `26c. Correctly failed 3 invalid/duplicate rows (failed=${mixedBatchData.failed})`);
  assert(Array.isArray(mixedBatchData.results), "29. Row-level errors returned in results array");

  // 31-33. S3 & Presigned resume URL verification
  console.log("\n[S3 & Presigned URL Verification]");
  const resumeFileContent = "%PDF-1.4 Test Resume Content";
  const resumeBoundary = "----WebKitFormBoundaryResume7MA4YW";
  const resumeUploadBody = `--${resumeBoundary}\r\nContent-Disposition: form-data; name="file"; filename="sample_resume.pdf"\r\nContent-Type: application/pdf\r\n\r\n${resumeFileContent}\r\n--${resumeBoundary}--\r\n`;

  const resumeUploadRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/${createdCandidateId}/resume/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${adminToken}`,
      "Content-Type": `multipart/form-data; boundary=${resumeBoundary}`,
    },
    body: resumeUploadBody,
  });
  assert(resumeUploadRes.status === 200, `31. Resume uploaded through Django S3 backend HTTP 200 (${resumeUploadRes.status})`);

  const resumeFetchRes = await fetch(`${BASE_URL}/api/v1/admin/candidates/${createdCandidateId}/resume/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  const resumeFetchData = await resumeFetchRes.json();
  assert(resumeFetchRes.status === 200, `32. Presigned URL retrieved for uploaded resume HTTP 200 (${resumeFetchRes.status})`);
  assert(Boolean(resumeFetchData.url), `33. Presigned URL string returned: ${resumeFetchData.url?.slice(0, 40)}...`);

  // 34-35. Admin jobs & Company list endpoints
  console.log("\n[Admin Jobs & Company Selector Endpoints]");
  const adminJobsRes = await fetch(`${BASE_URL}/api/v1/jobs/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  assert(adminJobsRes.status === 200, `34. Admin jobs list via Django API HTTP 200 (${adminJobsRes.status})`);

  const companiesRes = await fetch(`${BASE_URL}/api/v1/companies/`);
  assert(companiesRes.status === 200, `35. Companies list via Django API HTTP 200 (${companiesRes.status})`);

  console.log(`\n========================================`);
  console.log(`Phase 20 Results: ${passed} passed, ${failed} failed`);
  console.log(`========================================\n`);

  if (failed > 0) {
    process.exit(1);
  }
}

run().catch((err) => {
  console.error("Test execution failed with error:", err);
  process.exit(1);
});
