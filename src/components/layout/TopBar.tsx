import { Link, useNavigate } from "@tanstack/react-router";
import { Bell, Search, HelpCircle } from "lucide-react";

import { SidebarTrigger } from "@/components/ui/sidebar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { doctor, notifications } from "@/lib/mock-data";

export function TopBar() {
  const unread = notifications.filter((n) => n.unread).length;
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur-md sm:px-6">
      <SidebarTrigger className="min-h-9 min-w-9" aria-label="Toggle navigation" />

      <form
        role="search"
        className="relative hidden max-w-sm flex-1 md:block"
        onSubmit={(e) => {
          e.preventDefault();
          const q = new FormData(e.currentTarget).get("q") as string;
          navigate({ to: "/search", search: { q: q ?? "" } });
        }}
      >
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          type="search"
          aria-label="Search patients, twins and predictions"
          placeholder="Search patients, twins, predictions…"
          name="q"
          className="pl-9"
        />
      </form>

      <div className="ml-auto flex items-center gap-1.5">
        <Button variant="ghost" size="icon" className="min-h-10 min-w-10" aria-label="Help center" asChild>
          <Link to="/help">
            <HelpCircle className="size-5" aria-hidden="true" />
          </Link>
        </Button>

        <Button variant="ghost" size="icon" className="relative min-h-10 min-w-10" aria-label={`Notifications, ${unread} unread`} asChild>
          <Link to="/notifications">
            <Bell className="size-5" aria-hidden="true" />
            {unread > 0 && (
              <span className="absolute right-1.5 top-1.5 flex size-4 items-center justify-center rounded-full bg-risk text-[10px] font-semibold text-risk-foreground">
                {unread}
              </span>
            )}
          </Link>
        </Button>

        <Link
          to="/profile"
          className="ml-1 flex items-center gap-2.5 rounded-full border border-border py-1 pl-1 pr-3 transition-colors hover:bg-muted"
        >
          <Avatar className="size-8">
            <AvatarFallback className="bg-primary-soft text-xs font-semibold text-primary">
              {doctor.initials}
            </AvatarFallback>
          </Avatar>
          <span className="hidden text-left leading-tight sm:block">
            <span className="block text-xs font-semibold">{doctor.name}</span>
            <span className="block text-[11px] text-muted-foreground">{doctor.role}</span>
          </span>
        </Link>
      </div>
    </header>
  );
}
