import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { handleLoggedInAuthPage } from "@/lib/auth-visitor";

export default async function EmployerLoginPage({
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
  await handleLoggedInAuthPage("employer", {
    hasError: !!params.error,
  });

  return (
    <AuthShell
      audience="employer"
      title="Post your first role."
      description="Create your employer account to post remote tech roles and get matched candidates in your dashboard."
    >
      <AuthForm
        mode="login"
        role="employer"
        next={params.next}
        error={params.error}
        details={params.details}
        email={params.email}
        showSignOut={params.error === "profile_missing"}
      />
    </AuthShell>
  );
}
