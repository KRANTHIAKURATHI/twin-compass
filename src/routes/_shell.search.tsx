import { useState } from "react";
import { PageErrorState, PageSkeleton, RouteErrorState } from "@/components/common/PageState";
import { createFileRoute, Link } from "@tanstack/react-router";
import { FileText, Search as SearchIcon, User, Boxes } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { RiskChip, StatusChip } from "@/components/common/StatusChip";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDocuments, usePatients } from "@/hooks/api";

export const Route = createFileRoute("/_shell/search")({
  validateSearch: (search: Record<string, unknown>) => ({ q: typeof search.q === "string" ? search.q : "" }),
  head: () => ({
    meta: [
      { title: "Search — OncoTwin" },
      { name: "description", content: "Search across patients, digital twins and clinical documents in one place." },
      { property: "og:title", content: "Search — OncoTwin" },
      { property: "og:description", content: "Search across patients, digital twins and clinical documents in one place." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  errorComponent: RouteErrorState,
  component: SearchPage,
});

function SearchPage() {
  const { q: initialQ } = Route.useSearch();
  const [q, setQ] = useState(initialQ);
  const term = q.trim().toLowerCase();

  // Real backend data via the shared hooks (same cache as the Patients and Documents pages). In dev mock mode
  // (no VITE_API_BASE_URL) the services return fixtures by their own, explicit configuration; nothing here
  // falls back to fixtures when a request fails.
  const patientsQuery = usePatients();
  const documentsQuery = useDocuments();

  const patientHits = term
    ? (patientsQuery.data ?? []).filter(
        (p) =>
          p.name.toLowerCase().includes(term) ||
          p.id.toLowerCase().includes(term) ||
          (p.hospital ?? "").toLowerCase().includes(term),
      )
    : [];
  const docHits = term
    ? (documentsQuery.data ?? []).filter(
        (d) =>
          d.name.toLowerCase().includes(term) ||
          (d.patient ?? "").toLowerCase().includes(term) ||
          (d.category ?? "").toLowerCase().includes(term),
      )
    : [];

  const loading = patientsQuery.isLoading || documentsQuery.isLoading;
  const failed = patientsQuery.isError || documentsQuery.isError;
  const retryFailed = () => {
    if (patientsQuery.isError) void patientsQuery.refetch();
    if (documentsQuery.isError) void documentsQuery.refetch();
  };

  return (
    <div className="mx-auto max-w-[1000px]">
      <PageHeader
        title="Search"
        description="Find patients, twins and documents across the workspace."
        crumbs={[{ label: "Home", to: "/" }, { label: "Search" }]}
      />

      <div className="relative mb-4">
        <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search patients, twins, documents…"
          aria-label="Global search"
          className="h-12 pl-10 text-base"
        />
      </div>

      {!term ? (
        <EmptyState icon={SearchIcon} title="Start typing to search" description="Try a patient name, patient ID, hospital or document type such as MRI." />
      ) : loading ? (
        <PageSkeleton variant="list" />
      ) : failed && patientHits.length + docHits.length === 0 ? (
        <PageErrorState
          title="Search is unavailable"
          description={`${patientsQuery.isError ? "Patients" : "Documents"} could not be loaded from the server. No results are shown rather than placeholder data.`}
          onRetry={retryFailed}
        />
      ) : patientHits.length + docHits.length === 0 ? (
        <EmptyState icon={SearchIcon} title={`No results for “${q}”`} description="Check the spelling or try a broader term." />
      ) : (
        <div className="space-y-5">
          {failed && (
            <PageErrorState
              title="Some results could not be loaded"
              description={`${patientsQuery.isError ? "Patients" : "Documents"} failed to load, so only the results below are shown.`}
              onRetry={retryFailed}
            />
          )}
          {patientHits.length > 0 && (
            <section>
              <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Patients · {patientHits.length}</h2>
              <div className="space-y-2">
                {patientHits.map((p) => (
                  <Card key={p.id} className="hover-lift">
                    <CardContent className="flex flex-wrap items-center gap-3">
                      <span className="flex size-9 items-center justify-center rounded-xl bg-primary-soft text-primary">
                        <User className="size-4" aria-hidden="true" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <Link to="/patients/$patientId" params={{ patientId: p.id }} className="text-sm font-medium hover:underline">
                          {p.name}
                        </Link>
                        <p className="text-xs text-muted-foreground">
                          {p.id} · Stage {p.stage} · {p.hospital}
                        </p>
                      </div>
                      <RiskChip level={p.risk} />
                      <Link to="/digital-twins" className="text-xs text-primary hover:underline">
                        <span className="flex items-center gap-1">
                          <Boxes className="size-3.5" aria-hidden="true" /> Twin
                        </span>
                      </Link>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          )}

          {docHits.length > 0 && (
            <section>
              <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Documents · {docHits.length}</h2>
              <div className="space-y-2">
                {docHits.map((d) => (
                  <Card key={d.id} className="hover-lift">
                    <CardContent className="flex flex-wrap items-center gap-3">
                      <span className="flex size-9 items-center justify-center rounded-xl bg-primary-soft text-primary">
                        <FileText className="size-4" aria-hidden="true" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <Link to="/documents" className="text-sm font-medium hover:underline">
                          {d.name}
                        </Link>
                        <p className="text-xs text-muted-foreground">
                          {d.patient} · {d.date}
                        </p>
                      </div>
                      {d.category ? <StatusChip tone="neutral">{d.category}</StatusChip> : null}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
