// Render PORT handling for the frontend server (run with `node --test tests/`).
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = fileURLToPath(new URL("..", import.meta.url));

function dockerCmd(): string[] {
  const dockerfile = readFileSync(new URL("../Dockerfile", import.meta.url), "utf8");
  const line = dockerfile.split("\n").find((l) => l.startsWith("CMD "));
  assert.ok(line, "Dockerfile has a CMD");
  return JSON.parse(line.slice(4)) as string[];
}

test("container command binds 0.0.0.0 and leaves the port to $PORT", () => {
  const cmd = dockerCmd();
  assert.ok(!cmd.includes("--port"), "a fixed --port would override Render's $PORT");
  assert.equal(cmd[cmd.indexOf("--host") + 1], "0.0.0.0");
  const dockerfile = readFileSync(new URL("../Dockerfile", import.meta.url), "utf8");
  assert.match(dockerfile, /process\.env\.PORT\|\|3000/); // healthcheck follows $PORT
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as {
    scripts: Record<string, string>;
  };
  assert.ok(!pkg.scripts["start"]?.includes("--port"));
});

async function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = createServer();
    srv.once("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const address = srv.address();
      srv.close(() => resolve(typeof address === "object" && address ? address.port : 0));
    });
  });
}

test("srvx serves on the PORT environment variable with the container's flags", async () => {
  const port = await freePort();
  const cmd = dockerCmd().slice(1); // drop "node"
  const entry = cmd.indexOf("--entry");
  cmd[entry + 1] = "./tests/fixtures/entry.mjs";
  const statik = cmd.indexOf("--static");
  cmd.splice(statik, 2); // no build output needed for this check

  const child = spawn(process.execPath, cmd, {
    cwd: root,
    env: { ...process.env, PORT: String(port), NODE_ENV: "production" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  child.stdout.on("data", (d) => (output += d));
  child.stderr.on("data", (d) => (output += d));
  try {
    let body = "";
    for (let i = 0; i < 50 && !body; i++) {
      try {
        body = await (await fetch(`http://127.0.0.1:${port}/`)).text();
      } catch {
        await new Promise((r) => setTimeout(r, 100));
      }
    }
    assert.equal(body, "ok", `server did not answer on PORT=${port}\n${output}`);
  } finally {
    child.kill();
  }
});
