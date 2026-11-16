import esbuild from "../../node_modules/esbuild/lib/main.js";
import { fileURLToPath } from "node:url";

// Use the JS API: on Linux the CLI path may be a native binary, not JS.
await esbuild.build({
  absWorkingDir: fileURLToPath(new URL("../", import.meta.url)),
  entryPoints: ["src/host-client.tsx"],
  bundle: true,
  format: "esm",
  platform: "browser",
  jsx: "automatic",
  define: { "process.env.NODE_ENV": '"production"' },
  outfile: "host/app.js",
});
