import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  getCurrentUser,
  getDashboardPath,
  getEffectiveRole,
} from "../services/roleService";
import "./Unauthorized.css";

/**
 * Unauthorized — the app's 403 page (routes /unauthorized and /forbidden).
 *
 * Rendered whenever a signed-in user is denied access to a page, a role, a
 * required permission, or a specific study. Reads the current user and role
 * from roleService, shows which path was attempted (passed via React Router
 * location state.from), and offers two actions:
 *   - Return to Dashboard  -> getDashboardPath(effectiveRole)
 *   - Request Access       -> the existing /access-request flow
 */
function Unauthorized() {
  const location = useLocation();
  const navigate = useNavigate();

  const currentUser = getCurrentUser();
  const role = getEffectiveRole(currentUser);
  const attemptedPath =
    (location.state as any)?.from || location.pathname || "";
  const dashboardPath = currentUser?.role
    ? getDashboardPath(role || currentUser.role)
    : "/login";

  return (
    <div className="unauthorized-page">
      <div className="unauthorized-card">
        <div className="unauthorized-code" aria-hidden="true">
          403
        </div>
        <h1 className="unauthorized-title">Access Denied</h1>
        <p className="unauthorized-subtitle">
          You don&apos;t have access to this page or study.
        </p>

        {attemptedPath && (
          <div className="unauthorized-path">
            <span className="unauthorized-path-label">Attempted path:</span>
            <code className="unauthorized-path-value">{attemptedPath}</code>
          </div>
        )}

        {currentUser?.email && (
          <p className="unauthorized-user">
            Signed in as <strong>{currentUser.email}</strong>
            {role ? <> ({role})</> : null}.
          </p>
        )}

        <div className="unauthorized-actions">
          <button
            type="button"
            className="unauthorized-btn unauthorized-btn-primary"
            onClick={() => navigate(dashboardPath)}
          >
            Return to Dashboard
          </button>
          <Link
            className="unauthorized-btn unauthorized-btn-secondary"
            to="/access-request"
            state={{ from: attemptedPath || undefined }}
          >
            Request Access
          </Link>
        </div>

        <p className="unauthorized-help">
          If you believe this is a mistake, contact your organization
          administrator or submit a request for access.
        </p>
      </div>
    </div>
  );
}

export default Unauthorized;