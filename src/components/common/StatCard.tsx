import type { LucideIcon } from "lucide-react";
import { TrendingDown, TrendingUp } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";

const toneMap = {
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning-foreground",
  risk: "bg-risk-soft text-risk",
} as const;

export function StatCard({
  label,
  value,
  delta,
  icon: Icon,
  tone = "primary",
}: {
  label: string;
  value: string;
  delta?: string;
  icon: LucideIcon;
  tone?: keyof typeof toneMap;
}) {
  const negative = delta?.startsWith("-");
  return (
    <Card className="hover-lift gap-0 p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-xl", toneMap[tone])}>
          <Icon className="size-[18px]" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-3 font-display text-[26px] font-semibold leading-none tracking-tight">{value}</p>
      {delta && (
        <p
          className={cn(
            "mt-2.5 inline-flex items-center gap-1 text-xs font-medium",
            negative ? "text-risk" : "text-success",
          )}
        >
          {negative ? (
            <TrendingDown className="size-3.5" aria-hidden="true" />
          ) : (
            <TrendingUp className="size-3.5" aria-hidden="true" />
          )}
          {delta}
          <span className="font-normal text-muted-foreground">vs last month</span>
        </p>
      )}
    </Card>
  );
}
