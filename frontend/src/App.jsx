import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute, PublicOnly } from "./components/ProtectedRoute.jsx";
import { AppShell } from "./components/AppShell.jsx";

import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import VerifyEmail from "./pages/VerifyEmail.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";
import AcceptInvite from "./pages/AcceptInvite.jsx";
import OrgSetup from "./pages/OrgSetup.jsx";
import WorkspaceChoice from "./pages/WorkspaceChoice.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Expenses from "./pages/Expenses.jsx";
import Approvals from "./pages/Approvals.jsx";
import Budgets from "./pages/Budgets.jsx";
import Reports from "./pages/Reports.jsx";
import Insights from "./pages/Insights.jsx";
import Vendors from "./pages/Vendors.jsx";
import Team from "./pages/Team.jsx";
import Activity from "./pages/Activity.jsx";
import Settings from "./pages/Settings.jsx";

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<Landing />} />

      <Route
        path="/login"
        element={
          <PublicOnly>
            <Login />
          </PublicOnly>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnly>
            <Register />
          </PublicOnly>
        }
      />

      <Route path="/verify-email/:token" element={<VerifyEmail />} />
      <Route path="/verify-email" element={<VerifyEmail />} />

      <Route
        path="/forgot-password"
        element={
          <PublicOnly>
            <ForgotPassword />
          </PublicOnly>
        }
      />
      <Route
        path="/reset-password/:token"
        element={
          <PublicOnly>
            <ResetPassword />
          </PublicOnly>
        }
      />
      <Route
        path="/reset-password"
        element={
          <PublicOnly>
            <ResetPassword />
          </PublicOnly>
        }
      />

      {/* Invite flows */}
      <Route path="/accept-invite/:token" element={<AcceptInvite />} />
      <Route path="/invite" element={<AcceptInvite />} />

      {/* Workspace setup – requires auth but not an org yet */}
      <Route
        path="/workspace/start"
        element={
          <ProtectedRoute requireOrg={false}>
            <WorkspaceChoice />
          </ProtectedRoute>
        }
      />
      <Route
        path="/organization/setup"
        element={
          <ProtectedRoute requireOrg={false}>
            <OrgSetup />
          </ProtectedRoute>
        }
      />

      {/* Protected – requires auth + organization */}
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/expenses" element={<Expenses />} />

        {/* Owner-only routes */}
        <Route
          path="/approvals"
          element={
            <ProtectedRoute roles={["OWNER", "Owner"]}>
              <Approvals />
            </ProtectedRoute>
          }
        />
        <Route
          path="/budgets"
          element={
            <ProtectedRoute roles={["OWNER", "Owner"]}>
              <Budgets />
            </ProtectedRoute>
          }
        />
        <Route
          path="/reports"
          element={
            <ProtectedRoute roles={["OWNER", "Owner"]}>
              <Reports />
            </ProtectedRoute>
          }
        />
        <Route
          path="/insights"
          element={
            <ProtectedRoute roles={["OWNER", "Owner"]}>
              <Insights />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendors"
          element={
            <ProtectedRoute roles={["OWNER", "Owner"]}>
              <Vendors />
            </ProtectedRoute>
          }
        />
        <Route
          path="/team"
          element={<Team />}
        />

        {/* Accessible to all roles */}
        <Route path="/activity" element={<Activity />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      {/* 404 – redirect to landing */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
