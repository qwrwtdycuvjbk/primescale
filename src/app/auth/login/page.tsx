import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { AuthShell } from "@/components/auth/AuthShell";
import { formatAuthErrorMessage } from "@/lib/auth-errors";
import { createClient } from "@/lib/supabase/server";
import { ErrorBanner } from "@/components/site/form";

export default async function LoginChooserPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; details?: string }>;
}) {
  const params = await searchParams;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user && !params.error) redirect("/auth/redirect");

  const authErrorMessage = formatAuthErrorMessage(
    params.error,
    params.details,
  );

  return (
    <AuthShell
      title="Welcome back."
      description="Choose how you use PrimeScale — employers post roles, candidates get matched to remote tech opportunities."
    >
      <div className="w-full space-y-4">
        {authErrorMessage && <ErrorBanner message={authErrorMessage} />}

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
