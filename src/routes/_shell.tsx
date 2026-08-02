import { Outlet, createFileRoute } from "@tanstack/react-router";

import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { TopBar } from "@/components/layout/TopBar";
import { RequireRole } from "@/components/auth/RequireRole";

export const Route = createFileRoute("/_shell")({
  component: ShellLayout,
});

function ShellLayout() {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-surface">
        <AppSidebar />
        <SidebarInset className="bg-surface">
          <TopBar />
          <main className="animate-in fade-in flex-1 px-4 py-6 duration-300 sm:px-6 lg:px-8">
            {/* Required: nested routes render here. */}
            <RequireRole roles={["doctor", "admin"]}>
        <Outlet />
      </RequireRole>
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
