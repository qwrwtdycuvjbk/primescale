import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export async function DashboardNav({
  role,
  name,
}: {
  role: "employer" | "candidate";
  name: string;
}) {
  const supabase = await createClient();

  async function signOut() {
    "use server";
    const client = await createClient();
    await client.auth.signOut();
    redirect("/");
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-lg font-bold text-slate-900">
            PrimeScale
          </Link>
          <nav className="hidden gap-6 text-sm text-slate-600 md:flex">
            {role === "employer" ? (
              <>
                <Link href="/employer" className="hover:text-slate-900">
                  Dashboard
                </Link>
                <Link href="/employer/jobs/new" className="hover:text-slate-900">
                  Post a role
                </Link>
              </>
            ) : (
              <>
                <Link href="/candidate" className="hover:text-slate-900">
                  Matches
                </Link>
                <Link href="/candidate/profile" className="hover:text-slate-900">
                  Profile
                </Link>
              </>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden text-sm text-slate-600 sm:inline">{name}</span>
          <form action={signOut}>
            <button
              type="submit"
              className="text-sm font-medium text-slate-600 hover:text-slate-900"
            >
              Sign out
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}
