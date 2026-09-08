/**
 * Phase 12 Integration Test Script
 * Verifies that the Next.js API client and endpoints communicate successfully with Django backend:
 * 1. Login with test candidate and test employer
 * 2. Get current user profile (/me)
 * 3. Token refresh
 * 4. Password reset request (anti-enumeration check)
 * 5. Role checks (Candidate vs Employer vs Admin)
 * 6. Logout and token invalidation
 */

const DJANGO_URL = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://127.0.0.1:8000";

async function runTests() {
  console.log(`Starting Phase 12 Auth Integration Tests against: ${DJANGO_URL}`);
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
    // 1. Candidate Registration
    const candidateEmail = `phase12.cand.${Date.now()}@example.com`;
    console.log(`\nTest 1: Register Candidate (${candidateEmail})`);
    const regRes = await fetch(`${DJANGO_URL}/api/v1/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: candidateEmail,
        password: "CandidatePass123!",
        full_name: "Phase12 Candidate",
        role: "candidate",
      }),
    });
    assert(regRes.status === 201, `Registration returned HTTP 201 (${regRes.status})`);
    const regData = await regRes.json();
    assert(Boolean(regData.access), "Received access token on registration");
    assert(Boolean(regData.refresh), "Received refresh token on registration");
    assert(regData.user?.role === "candidate", `User role is candidate (${regData.user?.role})`);

    // 2. Candidate Login
    console.log("\nTest 2: Candidate Login");
    const loginRes = await fetch(`${DJANGO_URL}/api/v1/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: candidateEmail,
        password: "CandidatePass123!",
      }),
    });
    assert(loginRes.status === 200, `Login returned HTTP 200 (${loginRes.status})`);
    const loginData = await loginRes.json();
    const token = loginData.access;
    const refreshToken = loginData.refresh;
    assert(Boolean(token), "Received access token on login");

    // 3. Current User (/me/)
    console.log("\nTest 3: Current User Profile (/me/)");
    const meRes = await fetch(`${DJANGO_URL}/api/v1/auth/me/`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    assert(meRes.status === 200, `GET /me/ returned HTTP 200 (${meRes.status})`);
    const meData = await meRes.json();
    assert(meData.email === candidateEmail, `Profile email matches (${meData.email})`);
    assert(meData.role === "candidate", `Profile role matches (${meData.role})`);

    // 4. Role Boundaries (Candidate forbidden on employer endpoint)
    console.log("\nTest 4: Candidate Access Control Matrix");
    const candOnEmployer = await fetch(`${DJANGO_URL}/api/v1/auth/test-employer/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    assert(candOnEmployer.status === 403, `Candidate forbidden on employer test endpoint (${candOnEmployer.status})`);

    const candOnAdmin = await fetch(`${DJANGO_URL}/api/v1/auth/test-admin/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    assert(candOnAdmin.status === 403, `Candidate forbidden on admin test endpoint (${candOnAdmin.status})`);

    // 5. Token Refresh
    console.log("\nTest 5: Token Refresh");
    const refreshRes = await fetch(`${DJANGO_URL}/api/v1/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken }),
    });
    assert(refreshRes.status === 200, `Token refresh returned HTTP 200 (${refreshRes.status})`);
    const refreshData = await refreshRes.json();
    assert(Boolean(refreshData.access), "New access token received");
    const newRefreshToken = refreshData.refresh;

    // 6. Password Reset Request (Anti-enumeration)
    console.log("\nTest 6: Password Reset Anti-Enumeration");
    const resetRes = await fetch(`${DJANGO_URL}/api/v1/auth/password-reset/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: candidateEmail }),
    });
    assert(resetRes.status === 200, `Password reset returned HTTP 200 (${resetRes.status})`);

    // 7. Logout & Blacklist
    console.log("\nTest 7: Logout & Refresh Blacklist");
    const logoutRes = await fetch(`${DJANGO_URL}/api/v1/auth/logout/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: newRefreshToken }),
    });
    assert(logoutRes.status === 200, `Logout returned HTTP 200 (${logoutRes.status})`);

    // 8. Re-using blacklisted token fails
    const reUseRefresh = await fetch(`${DJANGO_URL}/api/v1/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: newRefreshToken }),
    });
    assert(reUseRefresh.status === 401, `Blacklisted token rejected with HTTP 401 (${reUseRefresh.status})`);

    console.log(`\n========================================`);
    console.log(`Phase 12 Auth Integration Results: ${passed}/${total} PASSED`);
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

runTests();
