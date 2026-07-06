import Link from "next/link";
import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

const employerLinks = [
  { href: "/employer", label: "Dashboard" },
  { href: "/employer/matches", label: "Matches" },
  { href: "/employer/jobs", label: "Jobs" },
  { href: "/employer/company", label: "Company" },
];

export async function EmployerShell({
  children,
  name,
  activePath,
}: {
  children: React.ReactNode;
  name: string;
  activePath: string;
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
          <div className="flex items-center gap-8">
            <Link href="/">
              <PrimeScaleLogo variant="dark" />
            </Link>
            <nav className="hidden gap-1 md:flex">
              {employerLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    activePath === link.href ||
                    (link.href !== "/employer" && activePath.startsWith(link.href))
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
            <nav className="flex gap-1 md:hidden">
              {employerLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                    activePath === link.href ||
                    (link.href !== "/employer" && activePath.startsWith(link.href))
                      ? "bg-foreground text-background"
                      : "text-muted-foreground"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {name}
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
