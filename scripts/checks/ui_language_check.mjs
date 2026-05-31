#!/usr/bin/env node
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const ROOT = findRepoRoot();
const WEB_ROOT = path.join(ROOT, "web");
const require = createRequire(import.meta.url);
const ts = require(path.join(WEB_ROOT, "node_modules", "typescript"));

const PRIMARY_FILES = [
  "app/page.tsx",
  "app/inbox/page.tsx",
  "app/interventions/page.tsx",
  "app/learnings/page.tsx",
  "components/agent/CompensatingProposalControl.tsx",
  "components/agent/OperatorConsoleChat.tsx",
  "components/agent/operatorChatLogic.ts",
  "components/agent-runs/SelectedActionDetailPanel.tsx",
  "components/agent-runs/RunStartGuide.tsx",
  "components/interventions/InterventionStartGuide.tsx",
  "components/interventions/InterventionQueueSections.tsx",
  "components/interventions/interventionDisplay.ts",
  "components/learnings/InsightsStartGuide.tsx",
];

const INTERNAL_TERMS = [
  /\bpreflight\b/i,
  /\bcompensating (action|proposal)\b/i,
  /\bharness\b/i,
  /\bregistry\b/i,
  /\bposterior\b/i,
  /\bsnapshot\b/i,
  /\bhypothesis\b/i,
  /\bcalibration\b/i,
  /\bmemory artifact\b/i,
  /\bfingerprint\b/i,
];

function main() {
  const violations = [];
  for (const relativePath of PRIMARY_FILES) {
    const file = path.join(WEB_ROOT, relativePath);
    const source = fs.readFileSync(file, "utf8");
    const sourceFile = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    for (const text of collectCandidateText(sourceFile)) {
      for (const pattern of INTERNAL_TERMS) {
        if (pattern.test(text.value)) {
          violations.push(
            `${relativePath}:${text.line}: "${text.value.trim()}" matches ${pattern}`,
          );
        }
      }
    }
  }

  if (violations.length > 0) {
    console.error("Primary UI language check failed:");
    for (const violation of violations) {
      console.error(`- ${violation}`);
    }
    return 1;
  }

  console.log("Primary UI language check passed.");
  return 0;
}

function collectCandidateText(sourceFile) {
  const texts = [];
  function add(node, value) {
    const normalized = value.replace(/\s+/g, " ").trim();
    if (!normalized) return;
    texts.push({
      value: normalized,
      line: sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1,
    });
  }

  function visit(node) {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
      return;
    }
    if (ts.isJsxText(node)) {
      add(node, node.getText(sourceFile));
    } else if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      if (!isObjectPropertyName(node) && !isTypeOnlyLiteral(node)) {
        add(node, node.text);
      }
    } else if (ts.isTemplateExpression(node)) {
      add(node, [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join(" "));
    }
    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return texts;
}

function isObjectPropertyName(node) {
  return (
    node.parent &&
    ((ts.isPropertyAssignment(node.parent) && node.parent.name === node) ||
      (ts.isPropertySignature(node.parent) && node.parent.name === node))
  );
}

function isTypeOnlyLiteral(node) {
  return Boolean(
    node.parent &&
      (ts.isLiteralTypeNode(node.parent) ||
        ts.isImportTypeNode(node.parent) ||
        ts.isExternalModuleReference(node.parent)),
  );
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

process.exitCode = main();
