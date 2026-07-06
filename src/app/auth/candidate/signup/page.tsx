import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { createClient } from "@/lib/supabase/server";

export default async function CandidateSignupPage({
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
      title="Get matched."
      description="Create your candidate profile and let PrimeScale match you to US remote tech roles across AI, Cloud, Data, DevOps, and more."
    >
      <AuthForm
        mode="signup"
        role="candidate"
        error={params.error}
        details={params.details}
        awaiting={params.awaiting}
        email={params.email}
      />
    </AuthShell>
  );
}
