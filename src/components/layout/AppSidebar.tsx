import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Users,
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

const clinical = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Patients", url: "/patients", icon: Users },
  { title: "Digital Twins", url: "/digital-twins", icon: Boxes },
  { title: "Treatment Simulator", url: "/simulator", icon: FlaskConical },
  { title: "Predictions", url: "/predictions", icon: Brain },
  { title: "Explainability", url: "/explainability", icon: Lightbulb },
  { title: "Timeline", url: "/timeline", icon: History },
];

const documents = [
  { title: "Document Center", url: "/documents", icon: FolderOpen },
  { title: "OCR Verification", url: "/ocr", icon: ScanText },
  { title: "Search", url: "/search", icon: Search },
];

const insights = [
  { title: "Reports", url: "/reports", icon: FileText },
  { title: "Analytics", url: "/analytics", icon: BarChart3 },
];

const portals = [
  { title: "Patient Portal", url: "/portal", icon: HeartPulse },
  { title: "Admin Portal", url: "/admin/hospitals", icon: ShieldCheck },
  { title: "Research Portal", url: "/research/models", icon: Microscope },
];

const account = [
  { title: "Profile", url: "/profile", icon: User },
  { title: "Settings", url: "/settings", icon: Settings },
  { title: "Help & About", url: "/help", icon: LifeBuoy },
];


export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const pathname = useRouterState({ select: (r) => r.location.pathname });

  const isActive = (url: string) => (url === "/" ? pathname === "/" : pathname.startsWith(url));

  const renderGroup = (label: string, items: typeof clinical) => (
    <SidebarGroup>
      {!collapsed && <SidebarGroupLabel>{label}</SidebarGroupLabel>}
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => (
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
