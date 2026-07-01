import { Suspense } from "react";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { getSessionProfile } from "@/lib/auth";

export default async function CandidateSignupPage() {
  const { user } = await getSessionProfile();
  if (user) redirect("/auth/redirect");

  return (
    <AuthShell
      title="Get matched."
      description="Create your candidate profile and let PrimeScale match you to US remote tech roles across AI, Cloud, Data, DevOps, and more."
    >
      <Suspense
        fallback={
          <div className="text-center text-muted-foreground">Loading...</div>
        }
      >
        <AuthForm mode="signup" role="candidate" />
      </Suspense>
    </AuthShell>
  );
}
