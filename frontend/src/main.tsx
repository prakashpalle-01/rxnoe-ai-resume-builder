import React from "react";
import ReactDOM from "react-dom/client";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";
import "./index.css";
import { AppLayout } from "./components/layout";
import { AuthPage } from "./pages/auth";
import { DashboardPage } from "./pages/dashboard";
import { UploadResumePage } from "./pages/upload";
import { ResumeEditorPage } from "./pages/editor";
import { JobMatchPage } from "./pages/job-match";
import { DownloadPage } from "./pages/download";

function Protected({ children }: { children: React.ReactNode }) {
  return localStorage.getItem("rxnoe_token") ? children : <Navigate to="/login" replace />;
}

const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/dashboard" replace /> },
  { path: "/login", element: <AuthPage mode="login" /> },
  { path: "/signup", element: <AuthPage mode="signup" /> },
  {
    element: <Protected><AppLayout /></Protected>,
    children: [
      { path: "/dashboard", element: <DashboardPage /> },
      { path: "/upload-resume", element: <UploadResumePage /> },
      { path: "/resume-editor/:id", element: <ResumeEditorPage /> },
      { path: "/job-match/:resumeId", element: <JobMatchPage /> },
      { path: "/paste-job-description/:resumeId", element: <JobMatchPage /> },
      { path: "/ats-score/:resumeId", element: <JobMatchPage /> },
      { path: "/resume-preview/:id", element: <ResumeEditorPage /> },
      { path: "/download/:id", element: <DownloadPage /> },
      { path: "/export/:id", element: <DownloadPage /> }
    ]
  }
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
