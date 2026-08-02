import { createFileRoute, notFound } from "@tanstack/react-router";

import { RouteErrorState, withPageStates } from "@/components/common/PageState";
import { PageHeader } from "@/components/common/PageHeader";
import { PatientForm } from "@/components/patients/PatientForm";
import { patients, type Patient } from "@/lib/mock-data";

export const Route = createFileRoute("/_shell/patients/$patientId/edit")({
  loader: ({ params }) => {
    const patient = patients.find((p) => p.id === params.patientId);
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
  const { patient } = Route.useLoaderData() as { patient: Patient };
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
