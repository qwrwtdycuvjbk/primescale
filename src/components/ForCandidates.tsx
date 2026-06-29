import Link from "next/link";

export function ForCandidates() {
  return (
    <section id="for-candidates" className="bg-slate-50 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-600">
          For candidates
        </p>
        <h2 className="mt-3 max-w-xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Build your profile. Get matched to US tech roles.
        </h2>
        <p className="mt-4 max-w-2xl text-lg text-slate-600">
          No more applying into the void. Create one profile, set your skills and
          preferences, and let PrimeScale surface remote US tech opportunities
          that actually fit.
        </p>

        <ul className="mt-10 grid gap-4 sm:grid-cols-2">
          {[
            "One profile, ongoing matches",
            "US remote tech roles only",
            "AI scoring against real employer needs",
            "Mark roles you are interested in",
          ].map((item) => (
            <li
              key={item}
              className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 text-slate-700"
            >
              <span className="mt-1 text-teal-600">✓</span>
              {item}
            </li>
          ))}
        </ul>

        <Link
          href="/auth/signup?role=candidate"
          className="mt-10 inline-flex rounded-full bg-slate-900 px-8 py-4 text-base font-semibold text-white transition hover:bg-slate-800"
        >
          Create your profile
        </Link>
      </div>
    </section>
  );
}
