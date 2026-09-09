import { redirect } from "next/navigation";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import { isCompanyProfileComplete } from "@/lib/employer";
import { companiesApi, candidatesApi } from "@/lib/api";

export default async function AuthRedirectPage() {
  const { user, profile } = await getSessionProfile();

  if (!user || !profile) {
    redirect("/auth/login?error=session_missing");
  }

  if (profile.role === "admin") {
    redirect("/admin");
  }

  const token = await getAccessToken();

  if (profile.role === "employer") {
    let company = null;
    try {
      company = await companiesApi.getMyCompany({ token });
    } catch {
      // Company profile not found or network error
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
    // Candidate profile not found or network error
  }

  if (!candidateProfile || !isCandidateProfileComplete(candidateProfile)) {
    redirect("/candidate/onboarding");
  }

  redirect("/candidate");
}
