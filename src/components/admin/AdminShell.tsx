import Link from "next/link";
import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";
import { appContainerClass } from "@/components/site/layout";
import { loadAdminNavCounts } from "@/lib/admin-dashboard";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

function NavLink({
  href,
  label,
  activePath,
  badge,
}: {
  href: string;
  label: string;
  activePath: string;
  badge?: number;
}) {
  const isActive = activePath === href;

  return (
    <Link
      href={href}
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition ${
        isActive
          ? "bg-foreground text-background"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {label}
      {badge != null && badge > 0 && (
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
            isActive
              ? "bg-background text-foreground"
              : "bg-primary/15 text-primary"
          }`}
        >
          {badge}
        </span>
      )}
    </Link>
  );
}

export async function AdminShell({
  children,
  name,
  activePath = "/admin",
}: {
  children: React.ReactNode;
  name: string;
  activePath?: string;
}) {
  const counts = await loadAdminNavCounts();

  async function signOut() {
    "use server";
    const client = await createClient();
    await client.auth.signOut();
    redirect("/");
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-md">
        <div className={`${appContainerClass} flex items-center justify-between gap-6 py-4`}>
          <div className="flex flex-wrap items-center gap-4 lg:gap-6">
            <Link href="/admin">
              <PrimeScaleLogo variant="dark" />
            </Link>
            <nav className="flex flex-wrap gap-1">
              <NavLink href="/admin" label="Dashboard" activePath={activePath} />
              <NavLink href="/admin/candidates" label="Candidates" activePath={activePath} />
              <NavLink href="/admin/jobs" label="Jobs" activePath={activePath} />
              <NavLink href="/admin/job-leads" label="Job leads" activePath={activePath} />
              <NavLink
                href="/admin/matches"
                label="Match review"
                activePath={activePath}
                badge={counts.pendingMatches}
              />
              <NavLink
                href="/admin/handoffs"
                label="Handoffs"
                activePath={activePath}
                badge={counts.pendingHandoffs}
              />
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {name} · People Prime ops
            </span>
            <form action={signOut}>
              <button
                type="submit"
                className="text-sm font-medium text-muted-foreground transition hover:text-foreground"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}
