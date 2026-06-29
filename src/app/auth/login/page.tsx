import { Suspense } from "react";
import Link from "next/link";
import Image from "next/image";
import { AuthForm } from "@/components/auth/AuthForm";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-slate-50 px-6 py-12">
      <div className="mx-auto mb-10 max-w-md">
        <Link href="/">
          <Image
            src="/primescale-logo.png"
            alt="PrimeScale"
            width={200}
            height={116}
            className="h-10 w-auto"
          />
        </Link>
      </div>
      <Suspense fallback={<div className="text-center text-slate-500">Loading...</div>}>
        <AuthForm mode="login" />
      </Suspense>
    </div>
  );
}
