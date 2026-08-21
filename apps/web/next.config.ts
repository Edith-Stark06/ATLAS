import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

// `new URL(...).pathname` would do here on POSIX but yields "/D:/..." on
// Windows, which Next cannot canonicalize. fileURLToPath handles both.
const repoRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const nextConfig: NextConfig = {
  // Emits a self-contained server bundle with only the dependencies actually
  // reached, so the runtime image does not need node_modules. Turns a ~1GB
  // image into a ~200MB one.
  output: "standalone",

  // The web app is not at the repo root and dependencies are hoisted, so Next
  // has to be told where to trace from — otherwise the standalone build omits
  // packages that live in the root node_modules.
  outputFileTracingRoot: repoRoot,
};

export default nextConfig;
