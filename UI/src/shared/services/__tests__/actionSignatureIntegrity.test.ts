/**
 * Unit tests for the Part 11 signature integrity work (Task 3.3).
 *
 * Covers the pure, side-effect-free pieces of actionSignatureService:
 *   - the meaning taxonomy (SIGNATURE_MEANINGS / labels / helpers),
 *   - canonical JSON determinism (the backend _canonical_json contract),
 *   - the SHA-256 stamp: a real 64-char hex digest, deterministic for the
 *     same payload, sensitive to any field change (meaning / signer /
 *     timestamp / meta),
 *   - display helpers (formatSignatureStamp / formatSignatureTime).
 */

import {
  SIGNATURE_MEANINGS,
  SIGNATURE_MEANING_LABELS,
  canonicalJson,
  confirmLabelForAction,
  defaultMeaningForAction,
  formatSignatureStamp,
  formatSignatureTime,
  sha256Hex,
  signatureMeaningLabel,
  buildActionStamp,
} from "../actionSignatureService";

const IDENTITY = {
  displayName: "Jane Doe",
  email: "jane@test.local",
  role: "Admin",
  userId: "42",
};

describe("signature meaning taxonomy", () => {
  it("covers approval / review / authorship / verification", () => {
    const values = SIGNATURE_MEANINGS.map((m) => m.value);
    expect(values).toEqual(
      expect.arrayContaining(["approval", "review", "authorship", "verification"]),
    );
    expect(SIGNATURE_MEANING_LABELS.approval).toBe("Approval");
  });

  it("defaults meaning by action kind", () => {
    expect(defaultMeaningForAction("document:upload")).toBe("authorship");
    expect(defaultMeaningForAction("document:create")).toBe("authorship");
    expect(defaultMeaningForAction("document:delete")).toBe("approval");
    expect(defaultMeaningForAction("folder:rename")).toBe("review");
    expect(defaultMeaningForAction("folder:save")).toBe("review");
    expect(defaultMeaningForAction()).toBe("approval");
  });

  it("produces confirm labels per action kind", () => {
    expect(confirmLabelForAction("document:upload")).toBe("Upload & Sign");
    expect(confirmLabelForAction("document:delete")).toBe("Delete & Sign");
    expect(confirmLabelForAction("folder:rename")).toBe("Save & Sign");
    expect(confirmLabelForAction()).toBe("Sign & Sign");
  });

  it("labels meanings and falls back to the raw value", () => {
    expect(signatureMeaningLabel("approval")).toBe("Approval");
    expect(signatureMeaningLabel("verification")).toBe("Verification");
    expect(signatureMeaningLabel("custom")).toBe("custom");
  });
});

describe("canonical JSON (backend contract)", () => {
  it("is deterministic regardless of key insertion order", () => {
    const a = canonicalJson({ b: 1, a: { d: 2, c: 3 } });
    const b = canonicalJson({ a: { c: 3, d: 2 }, b: 1 });
    expect(a).toBe(b);
    expect(a).toBe('{"a":{"c":3,"d":2},"b":1}');
  });
});

describe("SHA-256 stamp", () => {
  it("returns a real 64-char hex digest", async () => {
    const digest = await sha256Hex("hello");
    expect(digest).toMatch(/^[0-9a-f]{64}$/);
    // SHA-256("hello") — known test vector.
    expect(digest).toBe(
      "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
    );
  });

  it("builds a deterministic stamp for the same payload", async () => {
    const payload = {
      actionKey: "eisf:sign",
      entityType: "eisf_document",
      entityName: "Informed Consent Form",
      meaning: "approval",
      signerIdentity: IDENTITY,
      timestamp: "2026-09-08T10:30:00.000Z",
      meta: { documentCode: "EISF-ABC", version: "1.0" },
    };
    const stamp = await buildActionStamp(payload);
    const again = await buildActionStamp(payload);
    expect(stamp).toBe(again);
    expect(stamp).not.toBe("Informed Consent Form"); // never the raw name
  });

  it("changes when any payload field changes (tamper-evidence)", async () => {
    const base = {
      actionKey: "eisf:sign",
      entityType: "eisf_document",
      entityName: "ICF v1",
      meaning: "approval",
      signerIdentity: IDENTITY,
      timestamp: "2026-09-08T10:30:00.000Z",
      meta: {},
    };
    const stamp = await buildActionStamp(base);

    const otherMeaning = await buildActionStamp({ ...base, meaning: "review" });
    const otherTime = await buildActionStamp({
      ...base,
      timestamp: "2026-09-08T11:00:00.000Z",
    });
    const otherName = await buildActionStamp({ ...base, entityName: "ICF v2" });
    const otherSigner = await buildActionStamp({
      ...base,
      signerIdentity: { ...IDENTITY, userId: "43" },
    });
    const otherMeta = await buildActionStamp({
      ...base,
      meta: { documentCode: "EISF-XYZ" },
    });

    expect(stamp).not.toBe(otherMeaning);
    expect(stamp).not.toBe(otherTime);
    expect(stamp).not.toBe(otherName);
    expect(stamp).not.toBe(otherSigner);
    expect(stamp).not.toBe(otherMeta);
  });
});

describe("display helpers", () => {
  it("truncates stamps and keeps short values", () => {
    expect(formatSignatureStamp("a".repeat(64))).toMatch(/…/);
    expect(formatSignatureStamp("short")).toBe("short");
    expect(formatSignatureStamp("")).toBe("—");
  });

  it("formats ISO times and falls back gracefully", () => {
    expect(formatSignatureTime("2026-09-08T10:30:00.000Z")).not.toBe("—");
    expect(formatSignatureTime("not-a-date")).toBe("not-a-date");
    expect(formatSignatureTime("")).toBe("—");
  });
});