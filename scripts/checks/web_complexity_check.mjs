#!/usr/bin/env node
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const ROOT = findRepoRoot();
const WEB_ROOT = path.join(ROOT, "web");
const require = createRequire(import.meta.url);
const ts = require(path.join(WEB_ROOT, "node_modules", "typescript"));

const SOURCE_DIRS = ["app", "components", "lib"];
const EXTRA_FILES = [
  "middleware.ts",
  "next.config.mjs",
  "playwright.config.ts",
  "vitest.config.ts",
  "vitest.setup.ts",
];
const SKIPPED_DIRS = new Set([".next", "node_modules"]);
const EXTENSIONS = [".ts", ".tsx"];
const DEFAULT_MAX_COMPLEXITY = 45;
const DEFAULT_MAX_INTERNAL_IMPORTS = 38;
const DEFAULT_MAX_DEPENDENCY_DEPTH = 12;
const DEFAULT_MAX_RELATIVE_PARENT_DEPTH = 2;

const FUNCTION_COMPLEXITY_LIMITS = new Map([
  ["app/admin/page.tsx#AdminPage", 209],
  ["app/agent-runs/page.tsx#AgentRunsPageContent", 323],
  ["app/alignment/page.tsx#AlignmentPage", 61],
  ["app/evidence/page.tsx#EvidencePage", 99],
  ["app/experiments/page.tsx#ExperimentsPageContent", 322],
  ["app/interventions/page.tsx#InterventionsPageContent", 51],
  ["app/lab-workspace.tsx#HomePageContent", 206],
  ["app/overview/page.tsx#OverviewPage", 56],
  ["app/simulation/page.tsx#SimulationPageContent", 335],
  ["app/simulation/page.tsx#<anonymous>", 50],
  ["app/validation/page.tsx#ValidationPageContent", 255],
  ["components/agent-runs/RegistryPanel.tsx#RegistryPanel", 131],
  ["components/agent-runs/SelectedActionDetailPanel.tsx#SelectedActionDetailPanel", 71],
  ["components/agent/OperatorConsoleChat.tsx#OperatorConsoleChat", 93],
  ["components/evidence/EvidencePanel.tsx#EvidencePanel", 121],
  ["components/experiments/useExperimentVariantActions.ts#useExperimentVariantActions", 60],
  ["components/layout/HistoryDrawer.tsx#HistoryDrawer", 61],
  ["components/layout/Sidebar.tsx#Sidebar", 55],
  ["components/simulation/SimulationPanel.tsx#SimulationPanel", 89],
]);
const APP_IMPORT_ALLOWLIST = new Set([
  "app/lab/page.tsx->app/lab-workspace.tsx",
  "app/runs/page.tsx->app/agent-runs/page.tsx",
]);

function main(argv) {
  const options = parseArgs(argv);
  const files = collectSourceFiles();
  const report = buildReport(files, options);
  if (options.reportJson) {
    fs.mkdirSync(path.dirname(options.reportJson), { recursive: true });
    fs.writeFileSync(options.reportJson, `${JSON.stringify(report, null, 2)}\n`);
  }

  printReport(report, options);
  if (report.violations.length > 0) {
    console.error("Frontend complexity violations found:");
    for (const violation of report.violations) {
      console.error(`- ${violation}`);
    }
    return 1;
  }
  console.log("Frontend complexity check passed.");
  return 0;
}

function parseArgs(argv) {
  const options = {
    maxComplexity: DEFAULT_MAX_COMPLEXITY,
    maxInternalImports: DEFAULT_MAX_INTERNAL_IMPORTS,
    maxDependencyDepth: DEFAULT_MAX_DEPENDENCY_DEPTH,
    maxRelativeParentDepth: DEFAULT_MAX_RELATIVE_PARENT_DEPTH,
    reportJson: "",
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];
    if (arg === "--max-complexity") {
      options.maxComplexity = Number(next);
      index += 1;
    } else if (arg === "--max-internal-imports") {
      options.maxInternalImports = Number(next);
      index += 1;
    } else if (arg === "--max-dependency-depth") {
      options.maxDependencyDepth = Number(next);
      index += 1;
    } else if (arg === "--max-relative-parent-depth") {
      options.maxRelativeParentDepth = Number(next);
      index += 1;
    } else if (arg === "--report-json") {
      options.reportJson = path.resolve(ROOT, next);
      index += 1;
    }
  }
  return options;
}

function buildReport(files, options) {
  const fileSet = new Set(files);
  const graph = new Map();
  const internalImportCounts = new Map();
  const complexityFindings = [];
  const violations = [];
  const appImportViolations = [];
  const relativeDepthViolations = [];

  for (const file of files) {
    const rel = relativeWebPath(file);
    const source = fs.readFileSync(file, "utf8");
    const sourceFile = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    const imports = collectImports(sourceFile);
    const resolvedImports = [];

    for (const importRecord of imports) {
      const parentDepth = relativeParentDepth(importRecord.specifier);
      if (parentDepth > options.maxRelativeParentDepth) {
        relativeDepthViolations.push(
          `${rel}:${importRecord.line}: relative import climbs ${parentDepth} parents (${importRecord.specifier})`,
        );
      }

      const resolved = resolveInternalImport(file, importRecord.specifier, fileSet);
      if (!resolved) {
        continue;
      }
      resolvedImports.push(resolved);
      const targetRel = relativeWebPath(resolved);
      if (isForbiddenAppImport(rel, targetRel)) {
        appImportViolations.push(`${rel}:${importRecord.line}: imports app module ${targetRel}`);
      }
    }

    internalImportCounts.set(rel, new Set(resolvedImports.map(relativeWebPath)).size);
    graph.set(rel, new Set(resolvedImports.map(relativeWebPath)));
    complexityFindings.push(...collectComplexities(sourceFile, rel));
  }

  const topComplexity = sortComplexity(complexityFindings).slice(0, 10);
  const complexFunctions = complexityFindings.filter((finding) => {
    const limit = FUNCTION_COMPLEXITY_LIMITS.get(`${finding.path}#${finding.name}`) ?? options.maxComplexity;
    return finding.score > limit;
  });
  const topInternalImports = [...internalImportCounts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 10);
  const [maxInternalImportsPath = "", maxInternalImports = 0] = topInternalImports[0] ?? [];
  const dependencyDepths = computeDependencyDepths(graph);
  const topDependencyDepths = [...dependencyDepths.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 10);
  const [maxDependencyDepthPath = "", maxDependencyDepth = 0] = topDependencyDepths[0] ?? [];
  const cycles = findCycles(graph);

  if (maxInternalImports > options.maxInternalImports) {
    violations.push(
      `max-internal-imports: value=${maxInternalImports} limit=${options.maxInternalImports} file=${maxInternalImportsPath}`,
    );
  }
  if (maxDependencyDepth > options.maxDependencyDepth) {
    violations.push(
      `max-dependency-depth: value=${maxDependencyDepth} limit=${options.maxDependencyDepth} file=${maxDependencyDepthPath}`,
    );
  }
  for (const finding of complexFunctions) {
    const limit = FUNCTION_COMPLEXITY_LIMITS.get(`${finding.path}#${finding.name}`) ?? options.maxComplexity;
    violations.push(`${finding.path}:${finding.line}: ${finding.name} complexity=${finding.score} limit=${limit}`);
  }
  for (const cycle of cycles) {
    violations.push(`import-cycle: ${cycle.join(" -> ")}`);
  }
  violations.push(...relativeDepthViolations, ...appImportViolations);

  return {
    metrics: {
      maxInternalImports: { value: maxInternalImports, limit: options.maxInternalImports, path: maxInternalImportsPath },
      maxDependencyDepth: { value: maxDependencyDepth, limit: options.maxDependencyDepth, path: maxDependencyDepthPath },
      complexity: { threshold: options.maxComplexity, violations: complexFunctions.length },
      importCycles: { violations: cycles.length },
      relativeImportDepth: { limit: options.maxRelativeParentDepth, violations: relativeDepthViolations.length },
      appImports: { violations: appImportViolations.length },
    },
    hotspots: {
      internalImports: topInternalImports.map(([file, count]) => ({ file, count })),
      dependencyDepths: topDependencyDepths.map(([file, depth]) => ({ file, depth })),
      complexity: topComplexity,
    },
    violations,
  };
}

function collectSourceFiles() {
  const files = [];
  for (const dir of SOURCE_DIRS) {
    walk(path.join(WEB_ROOT, dir), files);
  }
  for (const file of EXTRA_FILES) {
    const absolute = path.join(WEB_ROOT, file);
    if (fs.existsSync(absolute) && EXTENSIONS.includes(path.extname(absolute))) {
      files.push(absolute);
    }
  }
  return files.sort();
}

function walk(current, files) {
  if (!fs.existsSync(current)) {
    return;
  }
  const stat = fs.statSync(current);
  if (stat.isDirectory()) {
    if (SKIPPED_DIRS.has(path.basename(current))) {
      return;
    }
    for (const entry of fs.readdirSync(current)) {
      walk(path.join(current, entry), files);
    }
    return;
  }
  if (EXTENSIONS.includes(path.extname(current))) {
    files.push(current);
  }
}

function collectImports(sourceFile) {
  const imports = [];
  function visit(node) {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      imports.push({
        specifier: node.moduleSpecifier.text,
        line: lineFor(sourceFile, node),
      });
    }
    if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      const [specifier] = node.arguments;
      if (specifier && ts.isStringLiteral(specifier)) {
        imports.push({ specifier: specifier.text, line: lineFor(sourceFile, node) });
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return imports;
}

function collectComplexities(sourceFile, rel) {
  const findings = [];
  function visit(node) {
    if (
      ts.isFunctionDeclaration(node) ||
      ts.isMethodDeclaration(node) ||
      ts.isFunctionExpression(node) ||
      ts.isArrowFunction(node)
    ) {
      findings.push({
        path: rel,
        line: lineFor(sourceFile, node),
        name: functionName(node),
        score: cyclomaticComplexity(node),
      });
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return findings;
}

function cyclomaticComplexity(node) {
  let score = 1;
  function visit(child) {
    if (
      ts.isIfStatement(child) ||
      ts.isForStatement(child) ||
      ts.isForInStatement(child) ||
      ts.isForOfStatement(child) ||
      ts.isWhileStatement(child) ||
      ts.isDoStatement(child) ||
      ts.isCaseClause(child) ||
      ts.isCatchClause(child) ||
      ts.isConditionalExpression(child)
    ) {
      score += 1;
    } else if (
      ts.isBinaryExpression(child) &&
      (child.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken ||
        child.operatorToken.kind === ts.SyntaxKind.BarBarToken ||
        child.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken)
    ) {
      score += 1;
    }
    ts.forEachChild(child, visit);
  }
  ts.forEachChild(node, visit);
  return score;
}

function functionName(node) {
  if (node.name?.text) {
    return node.name.text;
  }
  const parent = node.parent;
  if (parent && ts.isVariableDeclaration(parent) && parent.name && ts.isIdentifier(parent.name)) {
    return parent.name.text;
  }
  if (parent && ts.isPropertyAssignment(parent) && parent.name && ts.isIdentifier(parent.name)) {
    return parent.name.text;
  }
  return "<anonymous>";
}

function resolveInternalImport(fromFile, specifier, fileSet) {
  if (!specifier.startsWith(".")) {
    return null;
  }
  const base = path.resolve(path.dirname(fromFile), specifier);
  for (const candidate of candidatePaths(base)) {
    if (fileSet.has(candidate)) {
      return candidate;
    }
  }
  return null;
}

function candidatePaths(base) {
  const candidates = [];
  for (const ext of EXTENSIONS) {
    candidates.push(`${base}${ext}`);
  }
  for (const ext of EXTENSIONS) {
    candidates.push(path.join(base, `index${ext}`));
  }
  return candidates;
}

function relativeParentDepth(specifier) {
  if (!specifier.startsWith(".")) {
    return 0;
  }
  return specifier.split("/").filter((part) => part === "..").length;
}

function isForbiddenAppImport(fromRel, targetRel) {
  const key = `${fromRel}->${targetRel}`;
  if (APP_IMPORT_ALLOWLIST.has(key)) {
    return false;
  }
  if (path.posix.dirname(fromRel) === path.posix.dirname(targetRel)) {
    return false;
  }
  if (fromRel.startsWith("app/") && targetRel.startsWith("app/")) {
    const fromSegment = appSegment(fromRel);
    const targetSegment = appSegment(targetRel);
    return fromSegment !== targetSegment && !targetRel.startsWith("app/layout.");
  }
  return !fromRel.startsWith("app/") && targetRel.startsWith("app/");
}

function appSegment(rel) {
  const parts = rel.split("/");
  return parts[1] ?? "";
}

function computeDependencyDepths(graph) {
  const cache = new Map();
  function depth(file, stack = new Set()) {
    if (stack.has(file)) {
      return 0;
    }
    if (cache.has(file)) {
      return cache.get(file);
    }
    const nextStack = new Set(stack);
    nextStack.add(file);
    const children = [...(graph.get(file) ?? [])];
    const value = 1 + Math.max(0, ...children.map((child) => depth(child, nextStack)));
    cache.set(file, value);
    return value;
  }
  return new Map([...graph.keys()].map((file) => [file, depth(file)]));
}

function findCycles(graph) {
  const cycles = new Set();
  const visiting = new Set();
  const visited = new Set();
  const stack = [];

  function visit(file) {
    if (visiting.has(file)) {
      const cycle = [...stack.slice(stack.indexOf(file)), file];
      cycles.add(canonicalCycle(cycle).join("\n"));
      return;
    }
    if (visited.has(file)) {
      return;
    }
    visiting.add(file);
    stack.push(file);
    for (const child of [...(graph.get(file) ?? [])].sort()) {
      visit(child);
    }
    stack.pop();
    visiting.delete(file);
    visited.add(file);
  }

  for (const file of [...graph.keys()].sort()) {
    visit(file);
  }
  return [...cycles].sort().map((cycle) => cycle.split("\n"));
}

function canonicalCycle(cycle) {
  const nodes = cycle.slice(0, -1);
  const rotations = nodes.map((_, index) => [...nodes.slice(index), ...nodes.slice(0, index)]);
  const canonical = rotations.sort((a, b) => a.join("\n").localeCompare(b.join("\n")))[0];
  return [...canonical, canonical[0]];
}

function sortComplexity(findings) {
  return [...findings].sort(
    (a, b) => b.score - a.score || a.path.localeCompare(b.path) || a.line - b.line,
  );
}

function lineFor(sourceFile, node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
}

function printReport(report, options) {
  console.log("Frontend complexity report:");
  console.log(
    `- max_internal_imports=${report.metrics.maxInternalImports.value} ` +
      `limit=${options.maxInternalImports} file=${report.metrics.maxInternalImports.path}`,
  );
  console.log(
    `- max_dependency_depth=${report.metrics.maxDependencyDepth.value} ` +
      `limit=${options.maxDependencyDepth} file=${report.metrics.maxDependencyDepth.path}`,
  );
  console.log(
    `- complexity_threshold=${options.maxComplexity} ` +
      `violations=${report.metrics.complexity.violations}`,
  );
  console.log(`- import_cycles=${report.metrics.importCycles.violations}`);
  console.log(`- relative_import_depth_violations=${report.metrics.relativeImportDepth.violations}`);
  console.log(`- app_import_violations=${report.metrics.appImports.violations}`);
}

function relativeWebPath(file) {
  return path.relative(WEB_ROOT, file).split(path.sep).join("/");
}

function findRepoRoot() {
  let current = process.cwd();
  while (current !== path.dirname(current)) {
    if (fs.existsSync(path.join(current, "Makefile")) && fs.existsSync(path.join(current, "web"))) {
      return current;
    }
    current = path.dirname(current);
  }
  return process.cwd();
}

process.exitCode = main(process.argv.slice(2));
