import Link from "next/link";

export function GetStarted() {
  return (
    <section id="get-started" className="bg-white px-6 py-24">
      <div className="mx-auto max-w-6xl text-center">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-600">
          Get started
        </p>
        <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Ready to join PrimeScale?
        </h2>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
          Choose your path. US remote tech roles only.
        </p>

        <div className="mt-12 grid gap-6 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 p-8 text-left">
            <h3 className="text-xl font-semibold text-slate-900">
              I&apos;m hiring
            </h3>
            <p className="mt-3 text-slate-600">
              Post a role, get AI-matched candidates, and shortlist from your
              dashboard.
            </p>
            <Link
              href="/auth/employer/signup"
              className="mt-6 inline-flex rounded-full bg-teal-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-teal-400"
            >
              Post a role
            </Link>
          </div>

          <div className="rounded-2xl border border-slate-200 p-8 text-left">
            <h3 className="text-xl font-semibold text-slate-900">
              I&apos;m a candidate
            </h3>
            <p className="mt-3 text-slate-600">
              Build your profile once and get matched to relevant US remote tech
              roles.
            </p>
            <Link
              href="/auth/candidate/signup"
              className="mt-6 inline-flex rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              Get matched
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
