import { createFileRoute, notFound } from "@tanstack/react-router";

import { EmptyState } from "@/components/common/EmptyState";
import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { StateNotice } from "@/components/common/StateNotice";
import { PageHeader } from "@/components/common/PageHeader";
import { PatientForm } from "@/components/patients/PatientForm";
import { Skeleton } from "@/components/ui/skeleton";
import { Boxes } from "lucide-react";
import { patientService } from "@/services";
import { queryKeys, usePatient } from "@/hooks/api";

export const Route = createFileRoute("/_shell/patients/$patientId/edit")({
  loader: async ({ params, context }) => {
    const patient = await context.queryClient.ensureQueryData({
      queryKey: queryKeys.patients.detail(params.patientId),
      queryFn: () => patientService.get(params.patientId),
    });
    if (!patient) throw notFound();
    return { patient };
  },
  head: ({ loaderData }) => {
    if (!loaderData) {
      return { meta: [{ title: "Patient unavailable — OncoTwin" }, { name: "robots", content: "noindex" }] };
    }
    const title = `Edit ${loaderData.patient.name} — OncoTwin`;
    const description = `Update demographics, biomarkers and treatment for ${loaderData.patient.name}.`;
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  errorComponent: RouteErrorState,
  component: withPageStates(EditPatientPage, { variant: "detail" }),
});

function EditPatientPage() {
  const { patientId } = Route.useParams();
  const { data: patient, isLoading, isError } = usePatient(patientId);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-[1100px] space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="mx-auto max-w-[1100px]">
        <StateNotice
          state="prediction-unavailable"
          title="Could not load this patient"
          description="Something went wrong fetching this patient's record. Try again shortly."
        />
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="mx-auto max-w-[1100px]">
        <EmptyState icon={Boxes} title="Patient not found" description="This patient record could not be located." />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title={`Edit ${patient.name}`}
        description="Changes re-sync the digital twin and refresh predictions."
        crumbs={[
          { label: "Home", to: "/" },
          { label: "Patients", to: "/patients" },
          { label: patient.name, to: "/patients/$patientId", params: { patientId: patient.id } },
          { label: "Edit" },
        ]}
      />
      <PatientForm mode="edit" patient={patient} />
    </div>
  );
}
