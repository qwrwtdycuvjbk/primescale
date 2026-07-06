import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { handleLoggedInAuthPage } from "@/lib/auth-visitor";
import { createClient } from "@/lib/supabase/server";

export default async function CandidateLoginPage({
  searchParams,
}: {
  searchParams: Promise<{
    next?: string;
    error?: string;
    details?: string;
    email?: string;
  }>;
}) {
  const params = await searchParams;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) {
    await handleLoggedInAuthPage(user, "candidate", {
      hasError: !!params.error,
      page: "login",
    });
  }

  return (
    <AuthShell
      title="Your next role."
      description="Log in to manage your profile, view AI-matched US remote tech roles, and track your applications."
    >
      <AuthForm
        mode="login"
        role="candidate"
        next={params.next}
        error={params.error}
        details={params.details}
        email={params.email}
        showSignOut={params.error === "profile_missing"}
      />
    </AuthShell>
  );
}
