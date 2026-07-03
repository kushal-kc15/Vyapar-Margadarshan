import { useEffect } from "react";
import { Navigate, useLocation, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { Spinner } from "./Feedback.jsx";
import {
  getInvitePath,
  getSafeNextPath,
  readPendingInviteToken,
  storePendingInviteToken,
} from "../lib/inviteFlow.js";

export function ProtectedRoute({ children, roles, requireOrg = true }) {
  const { user, token, loading, organization, role } = useAuth();
  const loc = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper">
        <Spinner size={20} className="text-ink-muted" />
      </div>
    );
  }
  if (!token || !user) {
    return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  }
  if (requireOrg && !organization) {
    return <Navigate to="/workspace/start" replace />;
  }
  if (roles && roles.length) {
    const allowedRoles = roles.map((item) => String(item).toUpperCase());
    if (!allowedRoles.includes(String(role ?? '').toUpperCase())) {
      return <Navigate to="/dashboard" replace />;
    }
  }
  return children;
}

export function PublicOnly({ children, resetIncompleteSession = false }) {
  const { user, token, loading, organization, logout } = useAuth();
  const [params] = useSearchParams();
  const invite = params.get("invite");
  const next = getSafeNextPath(params.get("next") || "");
  const pendingInvite = invite || readPendingInviteToken();
  const shouldResetSession = Boolean(
    resetIncompleteSession && token && user && !organization && !next && !pendingInvite,
  );

  useEffect(() => {
    if (invite) storePendingInviteToken(invite);
  }, [invite]);

  useEffect(() => {
    if (shouldResetSession) logout();
  }, [logout, shouldResetSession]);

  if (loading || shouldResetSession) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper">
        <Spinner size={20} className="text-ink-muted" />
      </div>
    );
  }
  if (token && user) {
    if (next) return <Navigate to={next} replace />;
    if (pendingInvite) return <Navigate to={getInvitePath(pendingInvite)} replace />;
    return (
      <Navigate
        to={organization ? "/dashboard" : "/workspace/start"}
        replace
      />
    );
  }
  return children;
}
