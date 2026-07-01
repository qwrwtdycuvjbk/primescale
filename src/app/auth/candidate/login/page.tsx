import { Suspense } from "react";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { getSessionProfile } from "@/lib/auth";

export default async function CandidateLoginPage() {
  const { user } = await getSessionProfile();
  if (user) redirect("/auth/redirect");

  return (
    <AuthShell
      title="Your next role."
      description="Log in to manage your profile, view AI-matched US remote tech roles, and track your applications."
    >
      <Suspense
        fallback={
          <div className="text-center text-muted-foreground">Loading...</div>
        }
      >
        <AuthForm mode="login" role="candidate" />
      </Suspense>
    </AuthShell>
  );
}
