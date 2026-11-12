import type { LucideIcon } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";

/**
 * A page whose data has no backend endpoint yet. It says so plainly instead of
 * showing invented records, and offers no actions that would pretend to succeed.
 */
export function NotConnectedPage({
  title,
  description,
  icon,
  what,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  /** What is missing, e.g. "Audit logs". */
  what: string;
}) {
  return (
    <div className="mx-auto max-w-[1300px]">
      <PageHeader title={title} description={description} />
      <EmptyState
        icon={icon}
        title={`${what} are not connected`}
        description="This page has no backend endpoint yet, so there is no data to show. Nothing here is sample data."
      />
    </div>
  );
}
