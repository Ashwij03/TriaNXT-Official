import { Navigate, useLocation, useParams, useSearchParams } from "react-router-dom";
import ROLES from "../constants/roles";
import {
  canAccessRoute,
  getAdminPreviewRole,
  getCurrentUser,
  getPIPreviewRole,
  getUserScopeRestrictions,
  hasPermission,
  isAdmin,
  restrictStudiesToUserScope,
} from "../services/roleService";
import { getStudies } from "../services/studyService";

/**
 * GuardedRoute — additive route guard for study-scoped and
 * permission-sensitive pages (sits alongside ProtectedRoute / PermissionRoute,
 * which remain untouched for existing routes).
 *
 * Enforces, in order:
 *   1. not signed in                     -> /login
 *   2. role not in `allowedRoles`        -> /unauthorized (attempted path in
 *                                           route state — never a silent block)
 *   3. `requiredPermission` unsatisfied  -> /unauthorized
 *   4. the URL names a study (`:id` param or `study`/`studyId`/`studyCode`
 *      query param) outside the user's assigned studies -> /unauthorized
 *
 * `studyIdFromParams` selects which route param holds the study code (e.g.
 * "id" for /study-dashboard/:id). Study codes are cross-checked against
 * getStudies() so a study that no longer exists also bounces to 403 instead
 * of rendering empty data.
 */
function GuardedRoute({
  children,
  allowedRoles,
  requiredPermission,
  studyIdFromParams,
}: any) {
  const location = useLocation();
  const params = useParams();
  const [searchParams] = useSearchParams();

  const isLoggedIn = localStorage.getItem("isLoggedIn");
  const currentUser = getCurrentUser();

  if (isLoggedIn !== "true" || !currentUser) {
    return <Navigate to="/login" replace />;
  }

  /* 1. Role gate — same preview-role allowances ProtectedRoute uses. */
  if (allowedRoles && !allowedRoles.includes(currentUser.role)) {
    const previewRole = getAdminPreviewRole();
    const adminPreviewAllowed =
      isAdmin(currentUser) && previewRole && allowedRoles.includes(previewRole);
    const piPreviewRole = getPIPreviewRole();
    const piPreviewAllowed =
      currentUser.role === ROLES.PI &&
      piPreviewRole &&
      allowedRoles.includes(piPreviewRole);
    if (!adminPreviewAllowed && !piPreviewAllowed) {
      return (
        <Navigate
          to="/unauthorized"
          replace
          state={{ from: location.pathname }}
        />
      );
    }
  }

  /* 2. Required-permission gate. */
  if (requiredPermission && !hasPermission(requiredPermission)) {
    return (
      <Navigate to="/unauthorized" replace state={{ from: location.pathname }} />
    );
  }

  /* 3. Per-study scope gate. */
  if (studyIdFromParams) {
    const studyId =
      (params[studyIdFromParams] || "").trim() ||
      (searchParams.get("study") || searchParams.get("studyId") || searchParams.get("studyCode") || "").trim();

    if (studyId) {
      const { studies } = getUserScopeRestrictions(currentUser);
      if (studies.length && !studies.includes(studyId)) {
        return (
          <Navigate
            to="/unauthorized"
            replace
            state={{ from: location.pathname }}
          />
        );
      }
      // No explicit scope list — cross-check the study still resolves for this
      // user (a deleted/renamed study bounces to 403 instead of empty data).
      const visibleStudies = restrictStudiesToUserScope(getStudies(), currentUser);
      if (
        visibleStudies.length > 0 &&
        !visibleStudies.some(
          (study: any) =>
            String(study?.code || "") === studyId ||
            String(study?.studyId || "") === studyId,
        )
      ) {
        return (
          <Navigate
            to="/unauthorized"
            replace
            state={{ from: location.pathname }}
          />
        );
      }
    }
  }

  /* 4. General route-access matrix (parity with ProtectedRoute). */
  if (!canAccessRoute(location.pathname, currentUser)) {
    return (
      <Navigate
        to="/unauthorized"
        replace
        state={{ from: location.pathname }}
      />
    );
  }

  return children;
}

/** Preconfigured guard for `/studies/:id`-style routes: reads the study code
 *  from the route's `:id` param (or a study/studyId/studyCode query param). */
export function StudyRouteGuard(props: any) {
  return <GuardedRoute {...props} studyIdFromParams="id" />;
}

export default GuardedRoute;