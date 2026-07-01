import Link from "next/link";

export function ForEmployers() {
  return (
    <section id="for-employers" className="bg-slate-950 px-6 py-24 text-white">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-400">
          For employers
        </p>
        <h2 className="mt-3 max-w-xl text-3xl font-bold tracking-tight sm:text-4xl">
          Post a US remote tech role. Get matched candidates.
        </h2>
        <p className="mt-4 max-w-2xl text-lg text-slate-300">
          Skip the flood of unqualified applicants. PrimeScale uses AI to match
          your role to pre-vetted engineers across AI, Cloud, Data, DevOps, and
          Cybersecurity, with People Prime as your staffing backstop.
        </p>

        <ul className="mt-10 grid gap-4 sm:grid-cols-2">
          {[
            "AI-assisted job description parsing",
            "Skill and seniority-based matching",
            "US remote tech roles only",
            "Shortlist candidates from your dashboard",
          ].map((item) => (
            <li
              key={item}
              className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/5 px-5 py-4 text-slate-200"
            >
              <span className="mt-1 text-teal-400">✓</span>
              {item}
            </li>
          ))}
        </ul>

        <Link
          href="/auth/employer/signup"
          className="mt-10 inline-flex rounded-full bg-teal-500 px-8 py-4 text-base font-semibold text-slate-950 transition hover:bg-teal-400"
        >
          Post a role for free
        </Link>
      </div>
    </section>
  );
}
