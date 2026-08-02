import type { ReactNode } from "react";
import {
  AlertTriangle,
  BrainCircuit,
  CircleSlash,
  Loader2,
  RefreshCw,
  ShieldQuestion,
} from "lucide-react";

import { cn } from "@/lib/utils";

export type SystemState =
  | "low-confidence"
  | "prediction-unavailable"
  | "model-updating"
  | "waiting-verification"
  | "simulation-running"
  | "twin-recalculating";

const config: Record<
  SystemState,
  { icon: typeof AlertTriangle; title: string; description: string; tone: "warning" | "muted" | "primary"; spin?: boolean }
> = {
  "low-confidence": {
    icon: AlertTriangle,
    title: "Low model confidence",
    description: "This output falls below the 80% confidence threshold. Confirm with clinical judgement before acting.",
    tone: "warning",
  },
  "prediction-unavailable": {
    icon: CircleSlash,
    title: "Prediction unavailable",
    description: "The digital twin does not yet have enough verified data to produce a prediction.",
    tone: "muted",
  },
  "model-updating": {
    icon: BrainCircuit,
    title: "Model updating",
    description: "A new model version is being rolled out. Predictions may be briefly unavailable.",
    tone: "primary",
    spin: false,
  },
  "waiting-verification": {
    icon: ShieldQuestion,
    title: "Waiting for doctor verification",
    description: "Extracted values must be verified before they reach the digital twin.",
    tone: "warning",
  },
  "simulation-running": {
    icon: Loader2,
    title: "Simulation running",
    description: "Scenarios are being projected forward on the digital twin. This usually takes a few seconds.",
    tone: "primary",
    spin: true,
  },
  "twin-recalculating": {
    icon: RefreshCw,
    title: "Twin recalculating",
    description: "New clinical data is being folded into the twin. Values shown are from the previous version.",
    tone: "primary",
    spin: true,
  },
};

const toneClasses = {
  warning: "border-warning/40 bg-warning/5 text-warning-foreground",
  muted: "border-border bg-muted/50 text-muted-foreground",
  primary: "border-primary/30 bg-primary-soft/60 text-primary",
} as const;

export function StateNotice({
  state,
  title,
  description,
  action,
  className,
}: {
  state: SystemState;
  title?: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  const c = config[state];
  const Icon = c.icon;
  return (
    <div
      role="status"
      className={cn("flex flex-wrap items-start gap-3 rounded-xl border p-4", toneClasses[c.tone], className)}
    >
      <Icon className={cn("mt-0.5 size-5 shrink-0", c.spin && "animate-spin")} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{title ?? c.title}</p>
        <p className="mt-0.5 text-sm opacity-90">{description ?? c.description}</p>
      </div>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  );
}
