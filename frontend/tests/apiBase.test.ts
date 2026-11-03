// Frontend API URL configuration (run with `node --test tests/`).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  DEFAULT_API_BASE,
  checkBuildApiBase,
  isAbsoluteApiBase,
  resolveApiBase,
} from "../src/lib/apiBase.ts";

test("unset or blank falls back to same-origin /api", () => {
  for (const raw of [undefined, null, "", "   "]) assert.equal(resolveApiBase(raw), DEFAULT_API_BASE);
});

test("absolute backend URL is used as-is without trailing slashes", () => {
  assert.equal(
    resolveApiBase("https://archlens-backend.onrender.com/"),
    "https://archlens-backend.onrender.com",
  );
  assert.equal(resolveApiBase(" https://api.example.com/base// "), "https://api.example.com/base");
  assert.equal(resolveApiBase("http://localhost:8000"), "http://localhost:8000");
});

test("relative paths are kept for proxied deployments", () => {
  assert.equal(resolveApiBase("/api/"), "/api");
  assert.equal(resolveApiBase("/"), "/api");
});

test("ambiguous or unsafe values are rejected", () => {
  for (const raw of [
    "archlens-backend.onrender.com",
    "//archlens-backend.onrender.com",
    "ftp://x.example",
    "https://x.example/?a=1",
    "https://x.example/#f",
    "https://user:pw@x.example",
    "api",
  ]) {
    assert.throws(() => resolveApiBase(raw), /VITE_API_BASE_URL/, raw);
  }
});

test("Render build requires an absolute URL", () => {
  assert.throws(() => checkBuildApiBase(undefined, true), /absolute URL/);
  assert.throws(() => checkBuildApiBase("/api", true), /absolute URL/);
  assert.equal(
    checkBuildApiBase("https://archlens-backend.onrender.com", true),
    "https://archlens-backend.onrender.com",
  );
  // Compose / local dev keep the proxied default.
  assert.equal(checkBuildApiBase(undefined, false), "/api");
  assert.ok(isAbsoluteApiBase("https://a.b") && !isAbsoluteApiBase("/api"));
});

test("config.ts and vite.config.ts both go through the validator", () => {
  const config = readFileSync(new URL("../src/lib/config.ts", import.meta.url), "utf8");
  assert.match(config, /resolveApiBase\(\s*import\.meta\.env\["VITE_API_BASE_URL"\]/);
  assert.doesNotMatch(config, /localhost/);
  const vite = readFileSync(new URL("../vite.config.ts", import.meta.url), "utf8");
  assert.match(vite, /checkBuildApiBase\(/);
  assert.match(vite, /ARCHLENS_REQUIRE_ABSOLUTE_API_URL/);
});

test("Dockerfile forwards the build args Render provides", () => {
  const dockerfile = readFileSync(new URL("../Dockerfile", import.meta.url), "utf8");
  for (const arg of ["VITE_API_BASE_URL", "VITE_DEMO_MODE", "ARCHLENS_REQUIRE_ABSOLUTE_API_URL"]) {
    assert.match(dockerfile, new RegExp(`ARG ${arg}=`));
  }
});
