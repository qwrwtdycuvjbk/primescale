import { PostRoleForm } from "./PostRoleForm";

export function PostRoleSection() {
  return (
    <section id="post-role" className="bg-white px-6 py-24">
      <div className="mx-auto max-w-2xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-600">
          Get started
        </p>
        <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Post a remote tech role
        </h2>
        <p className="mt-4 text-lg text-slate-600">
          Fill out the form below and the People Prime Worldwide team will send
          you vetted candidates within 24 hours. No cost to post.
        </p>

        <div className="mt-10">
          <PostRoleForm />
        </div>
      </div>
    </section>
  );
}
