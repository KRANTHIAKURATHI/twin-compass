import { cva, type VariantProps } from "class-variance-authority";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/mock-data";

const chipVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
  {
    variants: {
      tone: {
        neutral: "border-border bg-muted text-muted-foreground",
        primary: "border-transparent bg-primary-soft text-primary",
        success: "border-transparent bg-success-soft text-success",
        warning: "border-transparent bg-warning-soft text-warning-foreground",
        risk: "border-transparent bg-risk-soft text-risk",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export type ChipTone = NonNullable<VariantProps<typeof chipVariants>["tone"]>;

export function StatusChip({
  children,
  tone,
  dot = false,
  className,
}: {
  children: ReactNode;
  tone?: ChipTone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span className={cn(chipVariants({ tone }), className)}>
      {dot && <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />}
      {children}
    </span>
  );
}

export const riskTone: Record<RiskLevel, ChipTone> = {
  low: "success",
  moderate: "warning",
  high: "risk",
};

export function RiskChip({ level }: { level: RiskLevel }) {
  const label = { low: "Low risk", moderate: "Moderate risk", high: "High risk" }[level];
  return (
    <StatusChip tone={riskTone[level]} dot>
      {label}
    </StatusChip>
  );
}
