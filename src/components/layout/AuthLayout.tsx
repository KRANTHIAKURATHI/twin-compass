import type { ReactNode } from "react";
import { Activity, ShieldCheck, Brain, LineChart } from "lucide-react";

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="relative hidden flex-col justify-between bg-primary p-12 text-primary-foreground lg:flex">
        <div className="flex items-center gap-2.5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-primary-foreground/15">
            <Activity className="size-5" aria-hidden="true" />
          </span>
          <span className="font-display text-lg font-semibold">OncoTwin</span>
        </div>

        <div>
          <h2 className="max-w-md font-display text-3xl font-semibold leading-tight">
            AI-driven digital twins for personalized breast cancer care
          </h2>
          <p className="mt-4 max-w-md text-sm text-primary-foreground/80">
            Model disease progression, simulate treatment options and compare predicted outcomes — with explainability
            built in for every clinical decision.
          </p>
          <ul className="mt-8 space-y-3 text-sm">
            {[
              { icon: Brain, text: "Outcome prediction with calibrated confidence" },
              { icon: LineChart, text: "Side-by-side treatment scenario comparison" },
              { icon: ShieldCheck, text: "Hospital-grade privacy and audit trails" },
            ].map((f) => (
              <li key={f.text} className="flex items-center gap-3">
                <f.icon className="size-4 shrink-0" aria-hidden="true" />
                {f.text}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-primary-foreground/70">
          For clinical decision support only. Not a substitute for professional medical judgement.
        </p>
      </aside>

      <main className="flex items-center justify-center bg-surface px-4 py-12 sm:px-8">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Activity className="size-5" aria-hidden="true" />
            </span>
            <span className="font-display text-base font-semibold">OncoTwin</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
          <div className="mt-7">{children}</div>
          {footer && <div className="mt-6 text-center text-sm text-muted-foreground">{footer}</div>}
        </div>
      </main>
    </div>
  );
}
