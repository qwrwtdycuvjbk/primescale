const steps = [
  {
    number: "01",
    title: "Post your role",
    description:
      "Share the title, skills, seniority, and engagement model you need. Contract and C2H options available.",
  },
  {
    number: "02",
    title: "We source and screen",
    description:
      "People Prime taps a global network of engineers across AI, Cloud, Data, DevOps, Cybersecurity, and more. Every candidate is pre-vetted and interview-ready.",
  },
  {
    number: "03",
    title: "Review candidates fast",
    description:
      "Receive a focused shortlist within 24 hours. We handle onboarding, payroll, and compliance end to end so you can hire with confidence.",
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
          End-to-end staffing, built for speed
        </h2>
        <p className="mt-4 max-w-2xl text-lg text-slate-600">
          On PrimeScale, you post once and People Prime delivers talent to you.
          No public job board. No flood of unqualified applicants. Just
          interview-ready professionals matched to your role.
        </p>

        <div className="mt-16 grid gap-8 md:grid-cols-3">
          {steps.map((step) => (
            <div key={step.number} className="relative">
              <span className="text-5xl font-bold text-slate-400">
                {step.number}
              </span>
              <h3 className="mt-4 text-xl font-semibold text-slate-900">
                {step.title}
              </h3>
              <p className="mt-3 leading-relaxed text-slate-600">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
