// Node helper: read a JS file from argv[2], parse it with acorn, emit
// the ESTree AST as JSON on stdout. The Python transpiler consumes it.
//
// Resolves acorn from nexus/node_modules (sibling of client/) so the
// client has no Node dependencies of its own.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const nexusRequire = createRequire(resolve(__dirname, "../../../nexus/package.json"));
const { Parser } = nexusRequire("acorn");

const [, , filePath] = process.argv;
if (!filePath) {
  process.stderr.write("usage: parse_js.mjs <file>\n");
  process.exit(2);
}

const source = readFileSync(filePath, "utf8");
let ast;
try {
  ast = Parser.parse(source, {
    ecmaVersion: 2022,
    sourceType: "module",
    locations: true,
  });
} catch (err) {
  process.stderr.write(`parse error in ${filePath}: ${err.message}\n`);
  process.exit(1);
}

process.stdout.write(JSON.stringify(ast));
