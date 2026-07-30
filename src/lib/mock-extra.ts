/**
 * Additional mock datasets for the extended portals (patient, admin, research)
 * and the deeper clinical pages (labs, imaging, documents, OCR, audit).
 * TODO(backend): replace each export with FastAPI / database responses.
 */

export const labResults = [
  { date: "2026-06-28", panel: "CBC", marker: "Hemoglobin", value: "12.4", unit: "g/dL", range: "12.0–15.5", flag: "normal" },
  { date: "2026-06-28", panel: "CBC", marker: "WBC", value: "3.1", unit: "10⁹/L", range: "4.0–11.0", flag: "low" },
  { date: "2026-06-28", panel: "CBC", marker: "Platelets", value: "212", unit: "10⁹/L", range: "150–400", flag: "normal" },
  { date: "2026-06-12", panel: "Tumor markers", marker: "CA 15-3", value: "38", unit: "U/mL", range: "< 30", flag: "high" },
  { date: "2026-06-12", panel: "Tumor markers", marker: "CEA", value: "2.8", unit: "ng/mL", range: "< 5", flag: "normal" },
  { date: "2026-05-08", panel: "Hepatic", marker: "ALT", value: "54", unit: "U/L", range: "7–45", flag: "high" },
  { date: "2026-05-08", panel: "Hepatic", marker: "Bilirubin", value: "0.7", unit: "mg/dL", range: "0.2–1.2", flag: "normal" },
  { date: "2026-05-08", panel: "Cardiac", marker: "LVEF (echo)", value: "58", unit: "%", range: "> 50", flag: "normal" },
] as const;

export const imagingStudies = [
  { id: "IMG-901", modality: "MRI", region: "Breast, bilateral", date: "2026-06-20", finding: "Tumor volume reduced 22% vs. baseline", radiologist: "Dr. P. Nakamura", status: "Final" },
  { id: "IMG-874", modality: "CT", region: "Chest / abdomen", date: "2026-04-02", finding: "No distant metastatic disease", radiologist: "Dr. L. Farrow", status: "Final" },
  { id: "IMG-830", modality: "PET", region: "Whole body", date: "2026-01-18", finding: "SUVmax 6.1 in left upper quadrant lesion", radiologist: "Dr. A. Kaur", status: "Final" },
  { id: "IMG-802", modality: "Mammography", region: "Left breast", date: "2025-11-04", finding: "BI-RADS 5 spiculated mass", radiologist: "Dr. M. Ortega", status: "Final" },
];

export const documents = [
  { id: "DOC-1", name: "MRI_Breast_2026_06.pdf", category: "MRI", patient: "Amelia Hart", date: "2026-06-20", size: "8.2 MB", version: 3, status: "Verified" },
  { id: "DOC-2", name: "CT_Chest_2026_04.pdf", category: "CT", patient: "Amelia Hart", date: "2026-04-02", size: "6.1 MB", version: 1, status: "Verified" },
  { id: "DOC-3", name: "PET_WholeBody_2026_01.pdf", category: "PET", patient: "Noor Rahman", date: "2026-01-18", size: "11.4 MB", version: 2, status: "Pending OCR" },
  { id: "DOC-4", name: "Biopsy_Pathology_Panel.pdf", category: "Biopsy", patient: "Priya Raghavan", date: "2025-04-02", size: "820 KB", version: 1, status: "Verified" },
  { id: "DOC-5", name: "Bloodwork_Q2_2026.pdf", category: "Blood", patient: "Elena Costa", date: "2026-05-08", size: "142 KB", version: 4, status: "Needs review" },
  { id: "DOC-6", name: "MRI_Followup_2026_02.pdf", category: "MRI", patient: "Grace Okafor", date: "2026-02-11", size: "7.7 MB", version: 1, status: "Verified" },
  { id: "DOC-7", name: "Biopsy_Core_Left.pdf", category: "Biopsy", patient: "Sofia Marchetti", date: "2025-09-30", size: "980 KB", version: 2, status: "Verified" },
  { id: "DOC-8", name: "CBC_Panel_June.pdf", category: "Blood", patient: "Hana Yamamoto", date: "2026-06-28", size: "96 KB", version: 1, status: "Pending OCR" },
];

export const documentVersions = [
  { version: 3, date: "2026-06-21 09:14", author: "Dr. Sarah Whitmore", note: "Verified OCR fields, corrected tumor size" },
  { version: 2, date: "2026-06-20 18:02", author: "OCR Pipeline v2.4", note: "Re-extracted after image enhancement" },
  { version: 1, date: "2026-06-20 17:40", author: "R. Mensah (Radiology)", note: "Original upload" },
];

export const ocrFields = [
  { field: "Patient name", value: "Amelia Hart", confidence: 0.99 },
  { field: "Patient ID", value: "PT-1042", confidence: 0.97 },
  { field: "Study date", value: "2026-06-20", confidence: 0.96 },
  { field: "Modality", value: "MRI — breast, bilateral", confidence: 0.94 },
  { field: "Tumor size (mm)", value: "21", confidence: 0.88 },
  { field: "ER status", value: "Positive", confidence: 0.92 },
  { field: "PR status", value: "Positive", confidence: 0.9 },
  { field: "HER2 status", value: "Negative", confidence: 0.71 },
  { field: "Ki-67 (%)", value: "24", confidence: 0.64 },
  { field: "Nodes involved", value: "2", confidence: 0.58 },
];

export const simulationHistory = [
  { id: "SIM-4412", date: "2026-06-30", scenario: "AC-T + Trastuzumab", survival: "86%", response: "Likely responder", model: "twin-v2.4" },
  { id: "SIM-4380", date: "2026-05-14", scenario: "Endocrine only", survival: "74%", response: "Partial", model: "twin-v2.3" },
  { id: "SIM-4321", date: "2026-03-08", scenario: "Neoadjuvant chemo", survival: "81%", response: "Likely responder", model: "twin-v2.3" },
  { id: "SIM-4290", date: "2026-01-22", scenario: "Surgery + radiotherapy", survival: "79%", response: "Partial", model: "twin-v2.2" },
];

export const appointments = [
  { id: "AP-31", title: "Chemotherapy cycle 4", doctor: "Dr. Sarah Whitmore", date: "2026-08-04", time: "09:30", location: "Infusion suite B", status: "Confirmed" },
  { id: "AP-32", title: "Follow-up MRI", doctor: "Dr. P. Nakamura", date: "2026-08-19", time: "14:00", location: "Imaging, level 2", status: "Scheduled" },
  { id: "AP-33", title: "Oncology review", doctor: "Dr. Sarah Whitmore", date: "2026-09-02", time: "11:15", location: "Clinic 3", status: "Scheduled" },
  { id: "AP-30", title: "Bloodwork", doctor: "Lab services", date: "2026-07-21", time: "08:00", location: "Phlebotomy", status: "Completed" },
];

export const treatmentPlan = {
  regimen: "AC-T Chemotherapy + Trastuzumab",
  cycle: 3,
  totalCycles: 6,
  startedOn: "2026-02-10",
  nextDose: "2026-08-04",
  adherence: 92,
  sideEffects: [
    { name: "Fatigue", grade: "Grade 2", advice: "Rest, light activity, hydration" },
    { name: "Nausea", grade: "Grade 1", advice: "Anti-emetic 30 min before meals" },
    { name: "Neuropathy", grade: "Grade 1", advice: "Report worsening tingling immediately" },
  ],
  medications: [
    { name: "Doxorubicin", dose: "60 mg/m²", schedule: "Every 21 days" },
    { name: "Cyclophosphamide", dose: "600 mg/m²", schedule: "Every 21 days" },
    { name: "Trastuzumab", dose: "6 mg/kg", schedule: "Every 21 days" },
    { name: "Ondansetron", dose: "8 mg", schedule: "As needed" },
  ],
};

export const hospitals = [
  { id: "H-1", name: "Northfield Oncology Center", city: "San Francisco, US", beds: 420, doctors: 68, patients: 812, status: "Active" },
  { id: "H-2", name: "St. Marien Klinik", city: "Munich, DE", beds: 310, doctors: 42, patients: 517, status: "Active" },
  { id: "H-3", name: "Cedar Bay Cancer Institute", city: "Vancouver, CA", beds: 260, doctors: 35, patients: 388, status: "Onboarding" },
];

export const doctorsDirectory = [
  { id: "DR-01", name: "Dr. Sarah Whitmore", dept: "Medical Oncology", hospital: "Northfield", patients: 42, status: "Active" },
  { id: "DR-02", name: "Dr. Luis Alvarez", dept: "Surgical Oncology", hospital: "Northfield", patients: 31, status: "Active" },
  { id: "DR-03", name: "Dr. Priya Nakamura", dept: "Radiology", hospital: "St. Marien", patients: 0, status: "Active" },
  { id: "DR-04", name: "Dr. Amara Kaur", dept: "Nuclear Medicine", hospital: "Cedar Bay", patients: 12, status: "On leave" },
  { id: "DR-05", name: "Dr. Marc Ortega", dept: "Pathology", hospital: "Northfield", patients: 0, status: "Active" },
];

export const departments = [
  { id: "D-1", name: "Medical Oncology", head: "Dr. Sarah Whitmore", staff: 24, activeCases: 312 },
  { id: "D-2", name: "Surgical Oncology", head: "Dr. Luis Alvarez", staff: 18, activeCases: 144 },
  { id: "D-3", name: "Radiology", head: "Dr. Priya Nakamura", staff: 21, activeCases: 480 },
  { id: "D-4", name: "Pathology", head: "Dr. Marc Ortega", staff: 12, activeCases: 260 },
  { id: "D-5", name: "Nuclear Medicine", head: "Dr. Amara Kaur", staff: 9, activeCases: 88 },
];

export const platformUsers = [
  { id: "U-101", name: "Dr. Sarah Whitmore", email: "s.whitmore@northfield.health", role: "Doctor", lastActive: "2 min ago", status: "Active" },
  { id: "U-102", name: "Amelia Hart", email: "amelia.hart@mail.health", role: "Patient", lastActive: "1 h ago", status: "Active" },
  { id: "U-103", name: "Rui Mensah", email: "r.mensah@northfield.health", role: "Technician", lastActive: "Yesterday", status: "Active" },
  { id: "U-104", name: "Dr. Amara Kaur", email: "a.kaur@cedarbay.health", role: "Doctor", lastActive: "6 days ago", status: "Suspended" },
  { id: "U-105", name: "Ops Bot", email: "ops@oncotwin.ai", role: "Service", lastActive: "Just now", status: "Active" },
];

export const auditLogs = [
  { id: "A-9001", time: "2026-07-30 16:42", actor: "Dr. Sarah Whitmore", action: "Approved OCR extraction", target: "DOC-1", ip: "10.4.2.19" },
  { id: "A-9000", time: "2026-07-30 16:12", actor: "OCR Pipeline v2.4", action: "Extracted 10 fields", target: "DOC-1", ip: "internal" },
  { id: "A-8999", time: "2026-07-30 15:03", actor: "Dr. Luis Alvarez", action: "Updated patient record", target: "PT-1063", ip: "10.4.2.44" },
  { id: "A-8998", time: "2026-07-30 12:20", actor: "Admin", action: "Suspended user", target: "U-104", ip: "10.4.1.2" },
  { id: "A-8997", time: "2026-07-29 18:55", actor: "System", action: "Deployed model", target: "twin-v2.4", ip: "internal" },
];

export const permissionMatrix = [
  { capability: "View patients", doctor: true, patient: false, technician: true, admin: true },
  { capability: "Edit patient records", doctor: true, patient: false, technician: false, admin: true },
  { capability: "Upload documents", doctor: true, patient: true, technician: true, admin: true },
  { capability: "Approve OCR extraction", doctor: true, patient: false, technician: false, admin: true },
  { capability: "Run simulations", doctor: true, patient: false, technician: false, admin: false },
  { capability: "Manage users", doctor: false, patient: false, technician: false, admin: true },
  { capability: "Access audit logs", doctor: false, patient: false, technician: false, admin: true },
];

export const models = [
  { id: "M-1", name: "Progression Twin", version: "v2.4", task: "Tumor trajectory", auc: 0.91, status: "Production" },
  { id: "M-2", name: "Survival Net", version: "v1.8", task: "5-year survival", auc: 0.88, status: "Production" },
  { id: "M-3", name: "Response Classifier", version: "v3.1", task: "Treatment response", auc: 0.85, status: "Staging" },
  { id: "M-4", name: "OCR Field Extractor", version: "v2.4", task: "Document parsing", auc: 0.94, status: "Production" },
];

export const datasets = [
  { id: "DS-1", name: "Northfield Longitudinal Cohort", records: 12840, modalities: "Clinical + Imaging", updated: "2026-07-12" },
  { id: "DS-2", name: "METABRIC (public)", records: 1980, modalities: "Genomic + Clinical", updated: "2026-03-02" },
  { id: "DS-3", name: "TCGA-BRCA", records: 1097, modalities: "Genomic + Pathology", updated: "2025-12-19" },
  { id: "DS-4", name: "Multi-site OCR corpus", records: 44210, modalities: "Documents", updated: "2026-07-28" },
];

export const trainingRuns = [
  { id: "RUN-311", model: "Progression Twin", started: "2026-07-25 02:10", duration: "6 h 12 m", epochs: 120, loss: 0.084, status: "Completed" },
  { id: "RUN-310", model: "Response Classifier", started: "2026-07-19 22:40", duration: "3 h 48 m", epochs: 80, loss: 0.131, status: "Completed" },
  { id: "RUN-309", model: "Survival Net", started: "2026-07-11 04:00", duration: "1 h 55 m", epochs: 60, loss: 0.097, status: "Failed" },
  { id: "RUN-308", model: "OCR Field Extractor", started: "2026-07-02 01:30", duration: "9 h 05 m", epochs: 200, loss: 0.042, status: "Completed" },
];

export const modelVersions = [
  { version: "v2.4", released: "2026-07-29", auc: 0.91, notes: "Added imaging-derived volumetrics", stage: "Production" },
  { version: "v2.3", released: "2026-05-04", auc: 0.89, notes: "Recalibrated HER2 subgroup", stage: "Archived" },
  { version: "v2.2", released: "2026-02-18", auc: 0.87, notes: "New endocrine response head", stage: "Archived" },
  { version: "v2.1", released: "2025-11-30", auc: 0.85, notes: "Baseline twin release", stage: "Archived" },
];

export const performanceTrend = [
  { month: "Feb", auc: 0.85, precision: 0.81, recall: 0.79 },
  { month: "Mar", auc: 0.86, precision: 0.82, recall: 0.8 },
  { month: "Apr", auc: 0.87, precision: 0.84, recall: 0.82 },
  { month: "May", auc: 0.89, precision: 0.85, recall: 0.83 },
  { month: "Jun", auc: 0.9, precision: 0.86, recall: 0.85 },
  { month: "Jul", auc: 0.91, precision: 0.88, recall: 0.86 },
];

export const patientNotifications = [
  { id: "pn1", title: "Appointment confirmed", body: "Chemotherapy cycle 4 on 4 Aug, 09:30 — infusion suite B.", time: "2 h ago", unread: true },
  { id: "pn2", title: "New report available", body: "Your MRI report from 20 June has been verified by your doctor.", time: "Yesterday", unread: true },
  { id: "pn3", title: "Medication reminder", body: "Take Ondansetron 8 mg 30 minutes before meals.", time: "2 days ago", unread: false },
  { id: "pn4", title: "Message from care team", body: "Dr. Whitmore added a note to your treatment plan.", time: "5 days ago", unread: false },
];
