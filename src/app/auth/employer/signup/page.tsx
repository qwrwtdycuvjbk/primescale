import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
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
  if (user && !params.error) redirect("/auth/redirect");

  return (
    <AuthShell
      audience="employer"
      title="Post your first role."
      description="Create your employer account to post US remote tech roles and get matched candidates in your dashboard."
    >
      <AuthForm
        mode="signup"
        role="employer"
        error={params.error}
        details={params.details}
        awaiting={params.awaiting}
        email={params.email}
      />
    </AuthShell>
  );
}
