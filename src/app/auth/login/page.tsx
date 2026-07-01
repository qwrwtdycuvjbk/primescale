import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { AuthShell } from "@/components/auth/AuthShell";
import { getSessionProfile } from "@/lib/auth";

export default async function LoginChooserPage() {
  const { user } = await getSessionProfile();
  if (user) redirect("/auth/redirect");

  return (
    <AuthShell
      title="Welcome back."
      description="Choose how you use PrimeScale — employers post roles, candidates get matched to US remote tech opportunities."
    >
      <div className="w-full space-y-4">
        <Link
          href="/auth/employer/login"
          className="flex items-center justify-between rounded-2xl border border-border bg-card px-6 py-5 transition hover:border-foreground/20"
        >
          <div>
            <p className="font-medium text-foreground">I&apos;m hiring</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Employer log in
            </p>
          </div>
          <ArrowRight className="h-5 w-5 text-muted-foreground" />
        </Link>
        <Link
          href="/auth/candidate/login"
          className="flex items-center justify-between rounded-2xl border border-border bg-card px-6 py-5 transition hover:border-foreground/20"
        >
          <div>
            <p className="font-medium text-foreground">I&apos;m a candidate</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Candidate log in
            </p>
          </div>
          <ArrowRight className="h-5 w-5 text-muted-foreground" />
        </Link>
      </div>
    </AuthShell>
  );
}
