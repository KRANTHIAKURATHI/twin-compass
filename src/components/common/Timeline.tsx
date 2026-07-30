import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface TimelineItem {
  date: string;
  title: string;
  detail: string;
  kind?: "diagnosis" | "treatment" | "scan" | "note";
}

const kindColor = {
  diagnosis: "bg-risk",
  treatment: "bg-primary",
  scan: "bg-chart-5",
  note: "bg-success",
} as const;

export function Timeline({ items, children }: { items: TimelineItem[]; children?: ReactNode }) {
  return (
    <ol className="relative space-y-5 border-l border-border pl-6">
      {items.map((item) => (
        <li key={item.date + item.title} className="relative">
          <span
            className={cn(
              "absolute -left-[27px] top-1 size-2.5 rounded-full ring-4 ring-card",
              kindColor[item.kind ?? "note"],
            )}
            aria-hidden="true"
          />
          <p className="text-xs text-muted-foreground">{item.date}</p>
          <p className="text-sm font-medium">{item.title}</p>
          <p className="text-sm text-muted-foreground">{item.detail}</p>
        </li>
      ))}
      {children}
    </ol>
  );
}
