import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { handleLoggedInAuthPage } from "@/lib/auth-visitor";
import { createClient } from "@/lib/supabase/server";

export default async function EmployerSignupPage({
  searchParams,
}: {
  searchParams: Promise<{
    error?: string;
    details?: string;
    awaiting?: string;
    email?: string;
  }>;
}) {
  const params = await searchParams;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) {
    await handleLoggedInAuthPage(user, "employer", {
      hasError: !!params.error,
      page: "signup",
    });
  }

  return (
    <AuthShell
      audience="employer"
      title="Post your first role."
      description="Create your employer account to post remote tech roles and get matched candidates in your dashboard."
    >
      <AuthForm
        mode="signup"
        role="employer"
        error={params.error}
        details={params.details}
        awaiting={params.awaiting}
        email={params.email}
        showSignOut={!!params.error}
      />
    </AuthShell>
  );
}
