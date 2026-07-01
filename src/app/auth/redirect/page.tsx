import { redirect } from "next/navigation";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import { isCompanyProfileComplete } from "@/lib/employer";
import { ensureProfileForUser } from "@/lib/ensure-profile";
import { createClient } from "@/lib/supabase/server";

export default async function AuthRedirectPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/auth/login?error=session_missing");
  }

  let profile: { role: string; full_name: string } | null = null;

  try {
    profile = await ensureProfileForUser(supabase, user);
  } catch (profileError) {
    const details =
      profileError instanceof Error ? profileError.message : "Profile not found";
    redirect(
      `/auth/login?error=profile_missing&details=${encodeURIComponent(details)}`,
    );
  }

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
