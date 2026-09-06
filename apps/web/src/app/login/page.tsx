import { AtlasMark } from "@/components/layout/atlas-mark";
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
        <div className="mb-7 flex flex-col items-center text-center">
          <span className="mb-4 flex size-10 items-center justify-center rounded-md border border-primary/25 bg-primary/[0.08] p-2 text-primary">
            <AtlasMark />
          </span>
          <p className="text-headline-lg tracking-[0.14em] text-on-surface">ATLAS</p>
          <p className="mt-1.5 text-status-label uppercase text-outline">
            Governance Control Plane
          </p>
        </div>

        <LoginForm
          // Only ever a path on this origin — see the check in the form.
          next={params.next}
          expired={params.expired === "1"}
        />

        <p className="mt-5 text-center text-body-sm text-outline">
          Access is governed by role. Ask an administrator for an account.
        </p>
      </div>
    </main>
  );
}
