import { redirect } from "next/navigation";
import { getSessionProfile } from "@/lib/auth";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import { isAdminEmail, preferredRoleFromUser } from "@/lib/ensure-profile";
import { isCompanyProfileComplete } from "@/lib/employer";
import { createClient } from "@/lib/supabase/server";

export default async function AuthRedirectPage() {
  const { user, profile } = await getSessionProfile();

  if (!user) {
    redirect("/auth/login?error=session_missing");
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
    redirect("/admin/handoffs");
  }

  const supabase = await createClient();

  if (profile.role === "employer") {
    const { data: company } = await supabase
      .from("companies")
      .select("id, name, size, description, hq_city, industry, profile_complete")
      .eq("owner_id", user.id)
      .maybeSingle();

    if (!company || !isCompanyProfileComplete(company)) {
      redirect("/employer/onboarding");
    }

    redirect("/employer");
  }

  const { data: candidateProfile } = await supabase
    .from("candidate_profiles")
    .select("profile_complete, resume_url")
    .eq("user_id", user.id)
    .maybeSingle();

  if (!isCandidateProfileComplete(candidateProfile)) {
    redirect("/candidate/onboarding");
  }

  redirect("/candidate");
}
