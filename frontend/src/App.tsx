import { Route, BrowserRouter, Routes } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { DashboardPage } from "@/pages/DashboardPage";
import { EvaluationPage } from "@/pages/EvaluationPage";
import { IncidentAnalysisPage } from "@/pages/IncidentAnalysisPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { ThemeProvider } from "@/store/ThemeProvider";

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="incident-analysis" element={<IncidentAnalysisPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="evaluation" element={<EvaluationPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
