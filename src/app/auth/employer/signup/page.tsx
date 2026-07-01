import { Suspense } from "react";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { getSessionProfile } from "@/lib/auth";

export default async function EmployerSignupPage() {
  const { user } = await getSessionProfile();
  if (user) redirect("/auth/redirect");

  return (
    <AuthShell
      audience="employer"
      title="Post your first role."
      description="Create your employer account to post US remote tech roles and get matched candidates in your dashboard."
    >
      <Suspense
        fallback={
          <div className="text-center text-muted-foreground">Loading...</div>
        }
      >
        <AuthForm mode="signup" role="employer" />
      </Suspense>
    </AuthShell>
  );
}
