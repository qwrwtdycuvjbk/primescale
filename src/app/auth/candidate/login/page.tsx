import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { handleLoggedInAuthPage } from "@/lib/auth-visitor";

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
  await handleLoggedInAuthPage("candidate", {
    hasError: !!params.error,
  });

  return (
    <AuthShell
      title="Your next role."
      description="Log in to manage your profile, view matched remote tech roles, and track your applications."
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
