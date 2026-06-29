import { Suspense } from "react";
import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";

export default function LoginPage() {
  return (
    <AuthShell
      title="Welcome back."
      description="Log in to manage your roles, review matches, and connect with US remote tech talent on PrimeScale."
    >
      <Suspense
        fallback={
          <div className="text-center text-muted-foreground">Loading...</div>
        }
      >
        <AuthForm mode="login" />
      </Suspense>
    </AuthShell>
  );
}
