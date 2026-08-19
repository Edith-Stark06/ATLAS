import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export default function ConsoleLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="flex h-screen overflow-hidden bg-background text-on-background selection:bg-primary selection:text-on-primary">
      <Sidebar />
      <div className="ml-64 flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-container-padding">{children}</main>
      </div>
    </div>
  );
}
