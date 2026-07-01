import { Suspense } from "react";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { getSessionProfile } from "@/lib/auth";

export default async function EmployerLoginPage() {
  const { user } = await getSessionProfile();
  if (user) redirect("/auth/redirect");

  return (
    <AuthShell
      audience="employer"
      title="Hire faster."
      description="Post US remote tech roles, get AI-matched candidates, and shortlist from your dashboard — with People Prime as your staffing backstop."
    >
      <Suspense
        fallback={
          <div className="text-center text-muted-foreground">Loading...</div>
        }
      >
        <AuthForm mode="login" role="employer" />
      </Suspense>
    </AuthShell>
  );
}
