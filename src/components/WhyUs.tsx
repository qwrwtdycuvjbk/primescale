const benefits = [
  {
    title: "Pre-vetted, interview-ready talent",
    description:
      "Every candidate is screened before they reach you. No resume piles. Just professionals ready to interview.",
  },
  {
    title: "AI, Cloud, Data, and beyond",
    description:
      "Deep expertise across AI, Cloud, Data, DevOps, Cybersecurity, and other in-demand technology disciplines.",
  },
  {
    title: "Full lifecycle support",
    description:
      "We handle sourcing, screening, onboarding, payroll, and compliance end to end so your team can stay focused on building.",
  },
  {
    title: "Flexible engagement models",
    description:
      "Choose the model that fits your hiring plan with Contract and C2H options backed by 14+ years of global staffing experience.",
  },
];

export function WhyUs() {
  return (
    <section id="why-us" className="bg-slate-50 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-600">
          Why PrimeScale
        </p>
        <h2 className="mt-3 max-w-2xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Trusted by companies scaling their tech teams
        </h2>

        <div className="mt-6 max-w-3xl space-y-4 text-lg leading-relaxed text-slate-600">
          <p>
            Hiring senior tech talent in the US right now often means long
            timelines and high costs, especially for AI, Cloud, and Data roles.
          </p>
          <p>
            People Prime Worldwide is a global technology staffing partner
            helping companies access pre-vetted, interview-ready engineers and
            tech professionals across AI, Cloud, Data, DevOps, Cybersecurity,
            and more.
          </p>
          <p>
            With 14+ years of experience and 50,000+ successful deployments, we
            handle sourcing, screening, onboarding, payroll, and compliance end
            to end, with flexible models (Contract, C2H).
          </p>
        </div>

        <div className="mt-16 grid gap-6 sm:grid-cols-2">
          {benefits.map((benefit) => (
            <div
              key={benefit.title}
              className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
            >
              <h3 className="text-lg font-semibold text-slate-900">
                {benefit.title}
              </h3>
              <p className="mt-3 leading-relaxed text-slate-600">
                {benefit.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
