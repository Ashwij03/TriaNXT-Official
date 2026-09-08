/**
 * Demo directory users — one account per role for the demo/dev build.
 * ===================================================================
 * Consumed by seedDemoDirectoryUsers() in src/shared/services/adminService.ts
 * (which populates the User Directory from these records on first load).
 *
 * Role strings match the canonical ROLES constants in
 * src/shared/constants/roles.ts ("Admin" | "SiteStaff" | "PI" | "CRO" |
 * "Sponsor"), the same strings roleService.ts / Login.tsx use.
 */

/** Shared password for every demo account. */
export const DEMO_USER_PASSWORD = "TriaNXT@Demo2026";

export interface DemoUser {
  email: string;
  name: string;
  username: string;
  role: "Admin" | "SiteStaff" | "PI" | "CRO" | "Sponsor";
}

export const DEMO_USERS: DemoUser[] = [
  {
    email: "admin@trianxt.demo",
    name: "Alex Admin",
    username: "alexadmin",
    role: "Admin",
  },
  {
    email: "sarah@trianxt.demo",
    name: "Sarah Site",
    username: "sarahsite",
    role: "SiteStaff",
  },
  {
    email: "peter@trianxt.demo",
    name: "Peter PI",
    username: "peterpi",
    role: "PI",
  },
  {
    email: "chris@trianxt.demo",
    name: "Chris CRO",
    username: "chriscro",
    role: "CRO",
  },
  {
    email: "sponsor@trianxt.demo",
    name: "Sam Sponsor",
    username: "samsponsor",
    role: "Sponsor",
  },
];

export default DEMO_USERS;