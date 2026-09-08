import { redirect } from "next/navigation";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { ensureProfileForUser, isAdminEmail, preferredRoleFromUser } from "@/lib/ensure-profile";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import { isCompanyProfileComplete } from "@/lib/employer";
import { createClient } from "@/lib/supabase/server";
import { companiesApi, candidatesApi } from "@/lib/api";
import type { User } from "@supabase/supabase-js";

export default async function AuthRedirectPage() {
  const { user, profile: initialProfile } = await getSessionProfile();

  if (!user) {
    redirect("/auth/login?error=session_missing");
  }

  let profile = initialProfile;

  if (!profile) {
    const preferredRole = preferredRoleFromUser(user);
    const supabase = await createClient();

    try {
      await ensureProfileForUser(supabase, user as User, preferredRole);
    } catch {
      // getSessionProfile already retries with the service client
    }

    const retry = await getSessionProfile();
    profile = retry.profile;
  }

  if (!profile) {
    const params = new URLSearchParams({
      error: "profile_missing",
      details: "Could not load your profile.",
    });
    if (user.email) params.set("email", user.email);
    const preferredRole = preferredRoleFromUser(user);
    const loginPath =
      preferredRole === "employer" || isAdminEmail(user.email)
        ? "/auth/employer/login"
        : "/auth/candidate/login";
    redirect(`${loginPath}?${params.toString()}`);
  }

  if (profile.role === "admin") {
    redirect("/admin");
  }

  const token = await getAccessToken();

  if (profile.role === "employer") {
    // 1. Try Django companies API
    let company = null;
    try {
      company = await companiesApi.getMyCompany({ token });
    } catch {
      // Fall back to Supabase
    }

    if (!company) {
      const supabase = await createClient();
      const { data: sbCompany } = await supabase
        .from("companies")
        .select("id, name, size, description, hq_city, industry, profile_complete")
        .eq("owner_id", user.id)
        .maybeSingle();
      company = sbCompany;
    }

    if (!company || !isCompanyProfileComplete(company)) {
      redirect("/employer/onboarding");
    }

    redirect("/employer");
  }

  // Candidate
  let candidateProfile = null;
  try {
    candidateProfile = await candidatesApi.getMyProfile({ token });
  } catch {
    // Fall back to Supabase
  }

  if (!candidateProfile) {
    const supabase = await createClient();
    const { data: sbCandidate } = await supabase
      .from("candidate_profiles")
      .select("profile_complete, resume_url")
      .eq("user_id", user.id)
      .maybeSingle();
    candidateProfile = sbCandidate;
  }

  if (!isCandidateProfileComplete(candidateProfile)) {
    redirect("/candidate/onboarding");
  }

  redirect("/candidate");
}
