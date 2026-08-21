import { LoginForm } from "@/components/auth/login-form";

export const metadata = { title: "Sign in — ATLAS" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; expired?: string }>;
}) {
  const params = await searchParams;

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface-base px-6 py-16">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <p className="text-display-sm text-on-surface">ATLAS</p>
          <p className="mt-1 font-mono text-label-mono uppercase text-outline">
            AI Trust Operating System
          </p>
        </div>

        <LoginForm
          // Only ever a path on this origin — see the check in the form.
          next={params.next}
          expired={params.expired === "1"}
        />

        <p className="mt-6 text-center text-body-sm text-outline">
          Access is governed by role. Ask an administrator for an account.
        </p>
      </div>
    </main>
  );
}
