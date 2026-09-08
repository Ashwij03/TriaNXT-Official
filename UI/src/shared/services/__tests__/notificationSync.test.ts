/**
 * Unit tests for the Phase-1 v2 notification backend mirror
 * (notificationService.ts): backend-row -> record mapping and the
 * local/backend merge used to hydrate an empty store. These are the pure
 * helpers that define the /api/notifications contract on the client side.
 */

import {
  mergeNotifications,
  notificationRecordFromBackend,
} from "../notificationService";

describe("notificationRecordFromBackend", () => {
  it("maps a backend row to the local record shape", () => {
    const record = notificationRecordFromBackend({
      id: "NOTIF-a1",
      backendId: 7,
      title: "Subject added",
      message: "Subject SUB-004 added to STUDY-X by Jane - PI.",
      actorName: "Jane Doe",
      actorRole: "PI",
      studyCode: "STUDY-X",
      type: "subject_added",
      metadata: { subjectId: "SUB-004" },
      createdAt: "2026-09-08T10:00:00.000Z",
      read: true,
    });
    expect(record.id).toBe("NOTIF-a1");
    expect(record.backendId).toBe(7);
    expect(record.title).toBe("Subject added");
    expect(record.message).toBe("Subject SUB-004 added to STUDY-X by Jane - PI.");
    expect(record.actorName).toBe("Jane Doe");
    expect(record.studyCode).toBe("STUDY-X");
    expect(record.type).toBe("subject_added");
    expect(record.metadata).toEqual({ subjectId: "SUB-004" });
    expect(record.read).toBe(true);
  });

  it("accepts the snake-ish backend aliases (body / notificationType / isRead)", () => {
    const record = notificationRecordFromBackend({
      backendId: 3,
      body: "Body only",
      notificationType: "INFO",
      isRead: false,
      createdAt: "2026-09-08T09:00:00.000Z",
    });
    expect(record.message).toBe("Body only");
    expect(record.type).toBe("INFO");
    expect(record.read).toBe(false);
    // No client id -> stable fallback key derived from the backend id.
    expect(record.id).toBe("notif-3");
  });

  it("defaults safely for an empty row", () => {
    const record = notificationRecordFromBackend({});
    expect(record.title).toBe("");
    expect(record.message).toBe("");
    expect(record.metadata).toEqual({});
    expect(record.read).toBe(false);
  });
});

describe("mergeNotifications", () => {
  it("keeps local records and appends unknown backend rows newest-first", () => {
    const local = [
      { id: "L1", title: "Local one", createdAt: "2026-09-07T10:00:00.000Z", read: false },
    ];
    const merged = mergeNotifications(local, [
      { id: "B1", title: "Backend one", createdAt: "2026-09-09T10:00:00.000Z", read: true },
      { id: "B2", title: "Backend two", createdAt: "2026-09-06T10:00:00.000Z", read: false },
    ]);
    expect(merged).toHaveLength(3);
    // Sorted by createdAt descending.
    expect(merged.map((record) => record.id)).toEqual(["B1", "L1", "B2"]);
  });

  it("local records win over same-id backend rows", () => {
    const local = [
      { id: "X1", title: "Local version", createdAt: "2026-09-08T10:00:00.000Z", read: false },
    ];
    const merged = mergeNotifications(local, [
      { id: "X1", title: "Backend version", createdAt: "2026-09-08T10:00:00.000Z", read: true },
    ]);
    expect(merged).toHaveLength(1);
    expect(merged[0].title).toBe("Local version");
    expect(merged[0].read).toBe(false);
  });

  it("dedupes duplicate backend rows and maps their fields", () => {
    const merged = mergeNotifications([], [
      { id: "A", title: "T1", message: "M1", createdAt: "2026-09-08T10:00:00.000Z" },
      { id: "A", title: "T1 dup", createdAt: "2026-09-08T10:00:00.000Z" },
      { id: "B", title: "T2", message: "M2", createdAt: "2026-09-07T10:00:00.000Z" },
    ]);
    expect(merged).toHaveLength(2);
    expect(merged[0].message).toBe("M1"); // first occurrence mapped
  });

  it("returns the local list untouched when nothing new arrives", () => {
    const local = [{ id: "L1", title: "Only", createdAt: "2026-09-08T10:00:00.000Z" }];
    expect(mergeNotifications(local, [])).toBe(local);
    expect(mergeNotifications(local, [{ id: "L1", title: "Same" }])).toBe(local);
  });

  it("tolerates non-array inputs", () => {
    expect(mergeNotifications(undefined, undefined)).toEqual([]);
    expect(mergeNotifications(null as any, "nope" as any)).toEqual([]);
  });
});
