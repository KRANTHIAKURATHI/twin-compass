import { createFileRoute } from "@tanstack/react-router";

import { PageHeader } from "@/components/common/PageHeader";
import { PatientForm } from "@/components/patients/PatientForm";

export const Route = createFileRoute("/_shell/patients/new")({
  head: () => ({
    meta: [
      { title: "Add Patient — OncoTwin" },
      { name: "description", content: "Register a new breast cancer patient and initialise their digital twin." },
      { property: "og:title", content: "Add Patient — OncoTwin" },
      { property: "og:description", content: "Register a new breast cancer patient and initialise their digital twin." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AddPatientPage,
});

function AddPatientPage() {
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        title="Add patient"
        description="Capture demographics, biomarkers and treatment to create a digital twin."
        crumbs={[{ label: "Home", to: "/" }, { label: "Patients", to: "/patients" }, { label: "Add patient" }]}
      />
      <PatientForm mode="create" />
    </div>
  );
}
