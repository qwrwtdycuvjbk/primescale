import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { handleLoggedInAuthPage } from "@/lib/auth-visitor";

export default async function AdminLoginPage({
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
  await handleLoggedInAuthPage("admin", {
    hasError: !!params.error,
  });

  return (
    <AuthShell
      audience="candidate"
      title="Admin Portal."
      description="Sign in with your administrator credentials to access the People Remotely administrator dashboard."
    >
      <AuthForm
        mode="login"
        role="admin"
        next={params.next}
        error={params.error}
        details={params.details}
        email={params.email}
      />
    </AuthShell>
  );
}
