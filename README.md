# Onco Twin AI

Master Prompt for Lovable Frontend Development

You are a senior Frontend Engineer, UX Designer, and Healthcare SaaS Product Designer.

Your task is to build a modern, production-quality frontend for an AI-powered Clinical Decision Support System.

Do not build a generic hospital management system. Build a clean, professional healthcare AI platform similar in quality to modern SaaS products.

Project Name

AI-Driven Digital Twin for Personalized Breast Cancer Progression and Treatment Outcome Simulation

Project Goal

The application helps doctors create a virtual patient (Digital Twin), analyze breast cancer progression, simulate different treatment options, compare predicted outcomes, and support clinical decision-making.

The frontend should feel like software used in hospitals, research centers, or healthcare organizations.

Use modern UI/UX principles.

Design Style

Use a clean, minimal, professional medical interface.

Requirements:

Modern SaaS design

Soft color palette

White background

Light gray sections

Blue primary color

Green for successful predictions

Orange for warnings

Red for high-risk indicators

Rounded cards

Smooth animations

Responsive layout

Excellent spacing

Accessible typography

Avoid clutter.

The UI should look comparable to enterprise healthcare software.

Target Users

Doctors

Oncologists

Medical Researchers

Hospital Administrators

Authentication Pages

Create:

Login

Register

Forgot Password

Reset Password

Fields:

Doctor Name

Email

Password

Hospital

Specialization

Role

Remember Me

Professional healthcare branding.

Main Layout

After login, display:

Left Sidebar

Top Navigation

Main Content

Right Information Panel (optional)

Sidebar should include:

Dashboard

Patients

Digital Twins

Treatment Simulator

Predictions

Reports

Analytics

Profile

Settings

Logout

Dashboard

Create an executive dashboard.

Display cards for:

Total Patients

Active Digital Twins

High Risk Patients

Treatment Simulations

Successful Predictions

Average Survival Probability

Charts:

Patient Growth

Cancer Stage Distribution

Treatment Comparison

Prediction Accuracy (placeholder)

Risk Distribution

Recent Activity

Upcoming Follow-ups

Notifications

Patient Management

Create a page to manage patients.

Features:

Patient Table

Search

Filter

Sort

Pagination

Patient Details

Create Patient

Edit Patient

Delete Patient

Columns:

Patient ID

Name

Age

Cancer Stage

Tumor Size

ER Status

PR Status

HER2 Status

Current Treatment

Current Status

Last Updated

Clicking a patient opens the patient profile.

Patient Profile

Create a complete patient overview.

Sections:

Personal Information

Medical History

Clinical Information

Biomarkers

Treatment Timeline

Disease Timeline

Uploaded Reports

Current Digital Twin

Prediction Summary

Doctor Notes

Timeline visualization.

Digital Twin Page

This is the highlight of the application.

Display:

Virtual Patient Card

Current Health Status

Current Stage

Tumor Information

Current Treatment

Disease Timeline

Twin Status

Risk Level

Twin Last Updated

Visualization of the Digital Twin.

Include an interactive card showing the patient's virtual representation.

Treatment Simulator

Doctors can compare multiple treatment scenarios.

Layout:

Current Patient

↓

Scenario Cards

Each scenario displays:

Treatment Name

Predicted Response

Expected Tumor Change

Risk Level

Confidence Score

Predicted Survival

Side Effect Risk

Recovery Estimate

Display all scenarios side-by-side.

Highlight the recommended treatment.

Prediction Page

Display AI predictions.

Cards:

Disease Progression

Treatment Response

Survival Probability

Recurrence Risk

Prediction Confidence

Each prediction should include:

Confidence

Status

Risk Indicator

Explanation placeholder

Charts.

Explainability Page

Doctors should understand why predictions were made.

Create a page containing:

Feature Importance Chart

Prediction Explanation Card

Key Influencing Factors

Positive Factors

Negative Factors

Risk Breakdown

Leave placeholders for backend integration.

Reports

Generate professional reports.

Include:

Patient Summary

Digital Twin Summary

Prediction Summary

Treatment Comparison

Timeline

Clinical Notes

Export Buttons:

PDF

CSV

Print

Analytics

Create an analytics dashboard.

Charts:

Age Distribution

Cancer Stage Distribution

Treatment Frequency

Prediction Trends

Risk Trends

Survival Estimates

Hospital Statistics

Use interactive charts with placeholder data.

Notifications

Create a notification center.

Examples:

New Patient Added

Prediction Completed

Digital Twin Updated

Simulation Finished

System Alerts

Profile

Doctor profile.

Include:

Photo

Hospital

Department

Specialization

Experience

Email

Phone

Edit Profile

Change Password

Settings

Create settings pages.

General

Appearance

Notifications

Security

Language

Privacy

API Configuration (placeholder)

Components

Create reusable components.

Buttons

Cards

Tables

Charts

Badges

Progress Bars

Dialogs

Drawers

Forms

Timeline

Tabs

Accordions

Search Bar

Filters

Loading Skeletons

Empty States

Error Pages

Toast Notifications

Status Chips

Breadcrumbs

Pagination

UI States

Design:

Loading

Empty

Success

Error

Offline

Unauthorized

No Data

Responsiveness

Support:

Desktop

Tablet

Mobile

Animations

Use subtle animations.

Page transitions

Card hover

Button hover

Sidebar transitions

Chart loading

Skeleton loading

Do not overuse animations.

Accessibility

Use:

Semantic HTML

Keyboard navigation

ARIA labels

Accessible color contrast

Readable font sizes

Focus states

Code Quality

Generate clean, modular, maintainable code.

Use reusable components.

Organize folders properly.

Avoid duplicated code.

Follow React best practices.

Backend Integration

Do not implement backend logic.

Instead:

Create service layers.

Use mock data.

Structure API calls cleanly.

Add TODO comments where backend endpoints will be integrated.

The backend will later be built using FastAPI and Supabase.

Final Goal

The finished frontend should look like a real-world AI-powered healthcare platform used by oncologists. Every page should be polished, responsive, and production-ready, with realistic placeholder data and a clear structure that can later be connected to the AI models, Digital Twin engine, and Supabase backend.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/45d06e47-3b72-4e30-941b-1763451d5eb2).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
