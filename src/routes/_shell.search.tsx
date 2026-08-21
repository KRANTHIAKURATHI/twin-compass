import { useState } from "react";
import { PageErrorState, PageSkeleton, RouteErrorState, withPageStates } from "@/components/common/PageState";
import { createFileRoute, Link } from "@tanstack/react-router";
import { FileText, Search as SearchIcon, User, Boxes } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusChip } from "@/components/common/StatusChip";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useGlobalSearch } from "@/hooks/api";

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
  component: withPageStates(SearchPage, { variant: "list" }),
});

function SearchPage() {
  const { q: initialQ } = Route.useSearch();
  const [q, setQ] = useState(initialQ);
  const term = q.trim();

  const { data, isLoading, isError } = useGlobalSearch(term);
  const patientHits = data?.patients ?? [];
  const docHits = data?.documents ?? [];
  const reportHits = data?.reports ?? [];
  const totalHits = patientHits.length + docHits.length + reportHits.length;

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
      ) : isLoading ? (
        <PageSkeleton variant="list" />
      ) : isError ? (
        <PageErrorState title="Search failed" description="We couldn't complete that search. Please try again." />
      ) : totalHits === 0 ? (
        <EmptyState icon={SearchIcon} title={`No results for “${q}”`} description="Check the spelling or try a broader term." />
      ) : (
        <div className="space-y-5">
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
                        <p className="text-xs text-muted-foreground">{p.id}</p>
                      </div>
                      <StatusChip tone="neutral">Patient</StatusChip>
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
                        <p className="text-xs text-muted-foreground">{d.id}</p>
                      </div>
                      <StatusChip tone="neutral">Document</StatusChip>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          )}

          {reportHits.length > 0 && (
            <section>
              <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Reports · {reportHits.length}</h2>
              <div className="space-y-2">
                {reportHits.map((r) => (
                  <Card key={r.id} className="hover-lift">
                    <CardContent className="flex flex-wrap items-center gap-3">
                      <span className="flex size-9 items-center justify-center rounded-xl bg-primary-soft text-primary">
                        <Boxes className="size-4" aria-hidden="true" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <Link to="/reports" className="text-sm font-medium hover:underline">
                          {r.name}
                        </Link>
                        <p className="text-xs text-muted-foreground">{r.id}</p>
                      </div>
                      <StatusChip tone="neutral">Report</StatusChip>
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
