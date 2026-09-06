import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export default function ConsoleLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="min-h-screen bg-surface-base text-on-background">
      <Sidebar />
      {/* The rail is fixed, so the content column is offset rather than
          flexed — that keeps the main region a normal document scroller and
          the sticky top bar behaves. */}
      <div className="flex min-h-screen flex-col lg:pl-60">
        <Topbar />
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5 lg:px-6 lg:py-6">
          {children}
        </main>
      </div>
    </div>
  );
}
