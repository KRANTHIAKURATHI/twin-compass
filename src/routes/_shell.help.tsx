import { createFileRoute, Link } from "@tanstack/react-router";
import { Activity, BookOpen, LifeBuoy, Mail, ShieldCheck, Sparkles } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export const Route = createFileRoute("/_shell/help")({
  head: () => ({
    meta: [
      { title: "Help & About — OncoTwin" },
      { name: "description", content: "How OncoTwin digital twins work, model limitations, FAQs and how to reach clinical support." },
      { property: "og:title", content: "Help & About — OncoTwin" },
      { property: "og:description", content: "How OncoTwin digital twins work, model limitations, FAQs and how to reach clinical support." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: HelpPage,
});

const faqs = [
  {
    q: "How is a digital twin built?",
    a: "Each twin combines demographics, staging, biomarkers (ER/PR/HER2, Ki-67), imaging-derived tumor volumetrics and treatment exposure into a longitudinal model that projects tumor trajectory and survival.",
  },
  {
    q: "How accurate are the predictions?",
    a: "The production progression model reports an AUC of 0.91 on the Northfield longitudinal cohort. Every prediction ships with a calibrated confidence interval and a feature-attribution breakdown on the Explainability page.",
  },
  {
    q: "Why must OCR fields be verified?",
    a: "Extracted values below 80% confidence are flagged. A clinician must confirm or correct every field before it is written to the twin — no unverified value ever influences a prediction.",
  },
  {
    q: "Is this a diagnostic device?",
    a: "No. OncoTwin is clinical decision support. It augments, but never replaces, the judgement of the treating oncologist.",
  },
  {
    q: "Where is patient data stored?",
    a: "Data stays inside your hospital tenant with row-level access controls and a full audit trail of every read and write.",
  },
];

function HelpPage() {
  return (
    <div className="mx-auto max-w-[1000px]">
      <PageHeader
        title="Help & About"
        description="Understand the platform, the models behind it and how to get support."
        crumbs={[{ label: "Home", to: "/" }, { label: "Help & About" }]}
      />

      <Card className="mb-4 border-primary/25 bg-primary-soft/40">
        <CardContent className="flex flex-wrap items-start gap-4">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
            <Activity className="size-6" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold">OncoTwin — AI-driven digital twins for breast cancer</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              A clinical decision support platform that models disease progression, simulates treatment options and explains
              every prediction. Version 2.4 · Model suite twin-v2.4.
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        {[
          { icon: Sparkles, title: "Simulate first", desc: "Compare regimens side by side before committing to a plan." },
          { icon: ShieldCheck, title: "Verified inputs", desc: "OCR values require clinician sign-off before use." },
          { icon: BookOpen, title: "Explainable", desc: "Feature attribution accompanies every outcome estimate." },
        ].map((f) => (
          <Card key={f.title}>
            <CardContent>
              <f.icon className="size-5 text-primary" aria-hidden="true" />
              <p className="mt-3 text-sm font-medium">{f.title}</p>
              <p className="text-sm text-muted-foreground">{f.desc}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Frequently asked questions</CardTitle>
          <CardDescription>Clinical and technical answers</CardDescription>
        </CardHeader>
        <CardContent>
          <Accordion type="single" collapsible>
            {faqs.map((f, i) => (
              <AccordionItem key={f.q} value={`item-${i}`}>
                <AccordionTrigger className="text-left text-sm">{f.q}</AccordionTrigger>
                <AccordionContent className="text-sm text-muted-foreground">{f.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <LifeBuoy className="size-4 text-primary" aria-hidden="true" /> Need a hand?
          </CardTitle>
          <CardDescription>Clinical support responds within one business day.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button asChild>
            <a href="mailto:support@oncotwin.health">
              <Mail className="size-4" aria-hidden="true" /> Email support
            </a>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/settings">Open settings</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
