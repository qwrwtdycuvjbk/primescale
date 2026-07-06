import Link from "next/link";
import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export async function AdminShell({
  children,
  name,
  activePath = "/admin/handoffs",
}: {
  children: React.ReactNode;
  name: string;
  activePath?: string;
}) {
  const supabase = await createClient();

  async function signOut() {
    "use server";
    const client = await createClient();
    await client.auth.signOut();
    redirect("/");
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href="/">
              <PrimeScaleLogo variant="dark" />
            </Link>
            <nav className="flex gap-1">
              <Link
                href="/admin/matches"
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  activePath === "/admin/matches"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Match review
              </Link>
              <Link
                href="/admin/handoffs"
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  activePath === "/admin/handoffs"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Handoffs
              </Link>
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
