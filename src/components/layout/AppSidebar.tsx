import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Users,
  ListChecks,

  Boxes,
  FlaskConical,
  Brain,
  Lightbulb,
  FileText,
  BarChart3,
  User,
  Settings,
  LogOut,
  Activity,
  History,
  FolderOpen,
  ScanText,
  Search,
  HeartPulse,
  ShieldCheck,
  Microscope,
  LifeBuoy,
} from "lucide-react";


import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

import { roleLabels, ROLES, type Role } from "@/lib/roles";
import { useAuth } from "@/components/auth/AuthProvider";

interface NavItem {
  title: string;
  url: string;
  icon: typeof LayoutDashboard;
  roles: Role[];
}

const all: Role[] = ["doctor", "patient", "researcher", "admin"];

const clinical: NavItem[] = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard, roles: all },
  { title: "Patients", url: "/patients", icon: Users, roles: ["doctor", "admin"] },
  { title: "Digital Twins", url: "/digital-twins", icon: Boxes, roles: ["doctor", "researcher"] },
  { title: "Treatment Simulator", url: "/simulator", icon: FlaskConical, roles: ["doctor", "researcher"] },
  { title: "Simulation Runs", url: "/simulations", icon: ListChecks, roles: ["doctor", "researcher"] },

  { title: "Predictions", url: "/predictions", icon: Brain, roles: ["doctor", "researcher"] },
  { title: "Explainability", url: "/explainability", icon: Lightbulb, roles: ["doctor", "researcher"] },
  { title: "Timeline", url: "/timeline", icon: History, roles: ["doctor"] },
];

const documents: NavItem[] = [
  { title: "Document Center", url: "/documents", icon: FolderOpen, roles: ["doctor", "admin"] },
  { title: "OCR Verification", url: "/ocr", icon: ScanText, roles: ["doctor"] },
  { title: "Search", url: "/search", icon: Search, roles: all },
];

const insights: NavItem[] = [
  { title: "Reports", url: "/reports", icon: FileText, roles: ["doctor", "admin", "researcher"] },
  { title: "Analytics", url: "/analytics", icon: BarChart3, roles: ["doctor", "admin", "researcher"] },
];

const portals: NavItem[] = [
  { title: "Patient Portal", url: "/portal", icon: HeartPulse, roles: ["patient", "admin"] },
  { title: "Admin Portal", url: "/admin/hospitals", icon: ShieldCheck, roles: ["admin"] },
  { title: "Research Portal", url: "/research/models", icon: Microscope, roles: ["researcher", "admin"] },
];

const account: NavItem[] = [
  { title: "Profile", url: "/profile", icon: User, roles: all },
  { title: "Settings", url: "/settings", icon: Settings, roles: all },
  { title: "Help & About", url: "/help", icon: LifeBuoy, roles: all },
];


export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const pathname = useRouterState({ select: (r) => r.location.pathname });
  const { role, setRole } = useAuth();

  const isActive = (url: string) => (url === "/" ? pathname === "/" : pathname.startsWith(url));


  const renderGroup = (label: string, items: NavItem[]) => {
    const visible = items.filter((i) => i.roles.includes(role));
    if (visible.length === 0) return null;
    return (
    <SidebarGroup>
      {!collapsed && <SidebarGroupLabel>{label}</SidebarGroupLabel>}

      <SidebarGroupContent>
        <SidebarMenu>
          {visible.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton asChild isActive={isActive(item.url)} tooltip={item.title}>
                <Link to={item.url} className="flex items-center gap-3">
                  <item.icon className="size-4 shrink-0" aria-hidden="true" />
                  <span>{item.title}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
    );
  };


  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2.5 px-1.5 py-2">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Activity className="size-5" aria-hidden="true" />
          </span>
          {!collapsed && (
            <span className="flex flex-col leading-tight">
              <span className="font-display text-sm font-semibold">OncoTwin</span>
              <span className="text-xs text-muted-foreground">Clinical Decision AI</span>
            </span>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent>
        {renderGroup("Clinical", clinical)}
        {renderGroup("Documents", documents)}
        {renderGroup("Insights", insights)}
        {renderGroup("Portals", portals)}
        {renderGroup("Account", account)}

      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        {!collapsed && (
          <div className="px-1.5 pb-1">
            <label htmlFor="role-switch" className="text-xs text-muted-foreground">
              Viewing as
            </label>
            <select
              id="role-switch"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              className="mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {roleLabels[r]}
                </option>
              ))}
            </select>
          </div>
        )}
        <SidebarMenu>

          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="Logout">
              <Link to="/login" className="flex items-center gap-3 text-muted-foreground">
                <LogOut className="size-4 shrink-0" aria-hidden="true" />
                <span>Logout</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
