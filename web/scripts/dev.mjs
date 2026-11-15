import { spawn } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const flags = process.argv.slice(2).flatMap(argument => {
  if (argument === "--strictPort") return [];
  return [argument === "--host" ? "--hostname" : argument];
});
const child = spawn(process.execPath, [require.resolve("next/dist/bin/next"), "dev", ...flags], {stdio: "inherit"});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", code => process.exit(code ?? 1));
