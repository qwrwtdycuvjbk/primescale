import { redirect } from "next/navigation";

export default async function SignupRedirectPage({
  searchParams,
}: {
  searchParams: Promise<{ role?: string }>;
}) {
  const { role } = await searchParams;
  if (role === "employer") redirect("/auth/employer/signup");
  if (role === "candidate") redirect("/auth/candidate/signup");
  redirect("/auth/candidate/signup");
}
