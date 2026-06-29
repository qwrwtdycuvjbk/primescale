import { Suspense } from "react";
import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";

export default function SignupPage() {
  return (
    <AuthShell
      title="Join PrimeScale."
      description="Create your account as an employer or candidate. US remote tech roles only, backed by People Prime Worldwide."
    >
      <Suspense
        fallback={
          <div className="text-center text-muted-foreground">Loading...</div>
        }
      >
        <AuthForm mode="signup" />
      </Suspense>
    </AuthShell>
  );
}
