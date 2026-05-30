import { createHash } from "node:crypto";

export function hashContent(content) {
  return `sha256:${createHash("sha256").update(content, "utf8").digest("hex")}`;
}

export function stableJson(value) {
  return JSON.stringify(sortJson(value));
}

function sortJson(value) {
  if (Array.isArray(value)) {
    return value.map(sortJson);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entryValue]) => [key, sortJson(entryValue)])
    );
  }
  return value;
}
