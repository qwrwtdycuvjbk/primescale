import Link from "next/link";

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-slate-950 px-6 pb-24 pt-20">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-teal-500/20 via-slate-950 to-slate-950" />
      <div
        className="pointer-events-none absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />

      <div className="relative mx-auto max-w-6xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 px-4 py-1.5 text-sm text-teal-300">
          <span className="h-2 w-2 rounded-full bg-teal-400" />
          AI-powered US remote tech hiring
        </div>

        <h1 className="mt-8 max-w-3xl text-4xl font-bold leading-tight tracking-tight text-white sm:text-5xl lg:text-6xl">
          Match US tech talent to the right roles.{" "}
          <span className="text-teal-400">Fast.</span>
        </h1>

        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-slate-300 sm:text-xl">
          PrimeScale is an AI hiring platform for US remote tech roles. Employers
          post roles. Candidates build a profile. Our matching engine connects
          both sides, backed by People Prime Worldwide&apos;s 14+ years in tech
          staffing.
        </p>

        <div className="mt-10 flex flex-col gap-4 sm:flex-row">
          <Link
            href="/auth/signup?role=employer"
            className="inline-flex items-center justify-center rounded-full bg-teal-500 px-8 py-4 text-base font-semibold text-slate-950 transition hover:bg-teal-400"
          >
            I&apos;m hiring
          </Link>
          <Link
            href="/auth/signup?role=candidate"
            className="inline-flex items-center justify-center rounded-full border border-white/20 px-8 py-4 text-base font-medium text-white transition hover:border-white/40 hover:bg-white/5"
          >
            I&apos;m a candidate
          </Link>
        </div>

        <div className="mt-16 grid gap-6 sm:grid-cols-3">
          {[
            { stat: "14+", label: "Years of staffing experience" },
            { stat: "50,000+", label: "Successful deployments" },
            { stat: "24h", label: "To matched, interview-ready talent" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm"
            >
              <p className="text-3xl font-bold text-teal-400">{item.stat}</p>
              <p className="mt-2 text-sm text-slate-400">{item.label}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
