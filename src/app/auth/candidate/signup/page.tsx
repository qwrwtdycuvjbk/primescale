import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { QueuePreferenceCapture } from "@/components/site/queue-preference-capture";
import { handleLoggedInAuthPage } from "@/lib/auth-visitor";
import { isRoleCategory } from "@/lib/matching-seats";

export default async function CandidateSignupPage({
  searchParams,
}: {
  searchParams: Promise<{
    error?: string;
    details?: string;
    awaiting?: string;
    email?: string;
    queue?: string;
  }>;
}) {
  const params = await searchParams;
  const queue = isRoleCategory(params.queue) ? params.queue : null;

  await handleLoggedInAuthPage("candidate", {
    hasError: !!params.error,
  });

  const title = queue ? `Join the ${queue} queue.` : "Get matched.";
  const description = queue
    ? `Create your candidate profile and join People Remotely’s matching queue for ${queue} remote tech seats.`
    : "Create your candidate profile and join a matching queue for remote tech roles across AI, Cloud, Data, DevOps, and more.";

  return (
    <AuthShell title={title} description={description}>
      <QueuePreferenceCapture queue={queue} />
      {queue ? (
        <p className="mb-4 rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
          Matching queue:{" "}
          <span className="font-semibold text-foreground">{queue}</span>
          . We’ll pre-select this category on your profile.
        </p>
      ) : null}
      <AuthForm
        mode="signup"
        role="candidate"
        error={params.error}
        details={params.details}
        awaiting={params.awaiting}
        email={params.email}
        showSignOut={!!params.error}
      />
    </AuthShell>
  );
}
