import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export default function ConsoleLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // No background colour here — the ambient gradient on <body> shows
    // through, which is what gives panels something to sit above.
    <div className="flex h-screen overflow-hidden text-on-background selection:bg-primary selection:text-on-primary">
      <Sidebar />
      <div className="ml-64 flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="custom-scrollbar flex-1 overflow-y-auto p-container-padding">
          {children}
        </main>
      </div>
    </div>
  );
}
