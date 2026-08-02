import type { LucideIcon, ReactNode } from "lucide-react";
import { Inbox } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { PageErrorState } from "@/components/common/PageState";
import { TableSkeleton } from "@/components/common/Skeletons";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
}

export function DataTablePage<T extends { id?: string }>({
  title,
  description,
  columns,
  rows,
  actions,
  children,
  loading = false,
  error = false,
  onRetry,
  emptyIcon,
  emptyTitle = "Nothing to show yet",
  emptyDescription = "Records will appear here once they are added.",
  emptyAction,
}: {
  title: string;
  description: string;
  columns: Column<T>[];
  rows: T[];
  actions?: ReactNode;
  children?: ReactNode;
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  emptyIcon?: LucideIcon;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-[1300px]">
      <PageHeader title={title} description={description} actions={actions} />
      {children}
      {loading ? (
        <TableSkeleton columns={columns.length} />
      ) : error ? (
        <PageErrorState onRetry={onRetry} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={emptyIcon ?? Inbox}
          title={emptyTitle}
          description={emptyDescription}
          action={emptyAction}
        />
      ) : (
        <Card className="overflow-hidden p-0">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((c) => (
                    <TableHead key={c.key}>{c.header}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, i) => (
                  <TableRow key={row.id ?? i}>
                    {columns.map((c) => (
                      <TableCell key={c.key}>{c.cell(row)}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

