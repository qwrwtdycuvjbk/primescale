import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { createClient } from "@/lib/supabase/server";

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
        mode="login"
        role="employer"
        next={params.next}
        error={params.error}
        details={params.details}
        email={params.email}
      />
    </AuthShell>
  );
}
