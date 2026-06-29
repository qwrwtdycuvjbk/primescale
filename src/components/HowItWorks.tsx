const employerSteps = [
  {
    number: "01",
    title: "Post your role",
    description:
      "Paste your JD or fill in details. AI helps structure the role for better matching.",
  },
  {
    number: "02",
    title: "Get matched candidates",
    description:
      "PrimeScale scores candidates against your stack, seniority, and US work requirements.",
  },
  {
    number: "03",
    title: "Shortlist and hire",
    description:
      "Review matches, shortlist the best fits, and move forward with People Prime support.",
  },
];

const candidateSteps = [
  {
    number: "01",
    title: "Build your profile",
    description:
      "Add your skills, experience, and US work authorization. No applying to dozens of listings.",
  },
  {
    number: "02",
    title: "Get matched to roles",
    description:
      "Our engine surfaces US remote tech roles that fit your profile and preferences.",
  },
  {
    number: "03",
    title: "Express interest",
    description:
      "Review matches, mark roles you want, and connect when there is mutual fit.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-white px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-600">
          How it works
        </p>
        <h2 className="mt-3 max-w-xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          One platform. Two paths.
        </h2>
        <p className="mt-4 max-w-2xl text-lg text-slate-600">
          PrimeScale connects US employers and remote tech professionals through
          AI-assisted matching, not endless job board scrolling.
        </p>

        <div className="mt-16 grid gap-16 lg:grid-cols-2">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">For employers</h3>
            <div className="mt-8 space-y-8">
              {employerSteps.map((step) => (
                <div key={step.number}>
                  <span className="text-4xl font-bold text-slate-300">
                    {step.number}
                  </span>
                  <h4 className="mt-2 text-lg font-semibold text-slate-900">
                    {step.title}
                  </h4>
                  <p className="mt-2 leading-relaxed text-slate-600">
                    {step.description}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-slate-900">For candidates</h3>
            <div className="mt-8 space-y-8">
              {candidateSteps.map((step) => (
                <div key={step.number}>
                  <span className="text-4xl font-bold text-slate-300">
                    {step.number}
                  </span>
                  <h4 className="mt-2 text-lg font-semibold text-slate-900">
                    {step.title}
                  </h4>
                  <p className="mt-2 leading-relaxed text-slate-600">
                    {step.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
