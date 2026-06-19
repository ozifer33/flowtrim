#!/usr/bin/env node
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";

const AGENTS = {
  claude: {
    label: "Claude Code",
    user: [".claude", "skills"],
    project: [".claude", "skills"],
  },
  codex: {
    label: "Codex",
    user: [".agents", "skills"],
    project: [".agents", "skills"],
  },
  copilot: {
    label: "GitHub Copilot",
    user: [".copilot", "skills"],
    project: [".github", "skills"],
  },
  "github-copilot": {
    label: "GitHub Copilot",
    user: [".copilot", "skills"],
    project: [".github", "skills"],
  },
};

const ALLOWLIST = ["SKILL.md", "references", "scripts", "agents"];

function main(argv) {
  const args = parseArgs(argv);
  if (args.help) {
    printHelp();
    return 0;
  }

  const agent = AGENTS[args.agent || ""];
  if (!agent) {
    throw new Error(`unsupported agent: ${args.agent || "(missing)"}`);
  }
  if (args.scope !== "user" && args.scope !== "project") {
    throw new Error("scope must be user or project");
  }

  const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const source = path.join(repoRoot, "skills", "flowtrim");
  if (!fs.existsSync(path.join(source, "SKILL.md"))) {
    throw new Error("FlowTrim skill source is missing");
  }

  const base =
    args.scope === "user"
      ? os.homedir()
      : path.resolve(args.project || process.cwd());
  const target = path.join(base, ...agent[args.scope], "flowtrim");

  if (args.dryRun) {
    console.log(`dry-run: would install flowtrim skill to ${target}`);
    return 0;
  }

  if (fs.existsSync(target) && !args.force) {
    throw new Error(`target already exists; rerun with --force: ${target}`);
  }
  if (fs.existsSync(target)) {
    removeDir(target);
  }

  fs.mkdirSync(target, { recursive: true });
  for (const item of ALLOWLIST) {
    const from = path.join(source, item);
    const to = path.join(target, item);
    if (fs.existsSync(from)) {
      copyRecursive(from, to);
    }
  }
  console.log(`installed flowtrim skill for ${agent.label}: ${target}`);
  return 0;
}

function parseArgs(argv) {
  const args = {
    agent: "",
    scope: "user",
    project: "",
    dryRun: false,
    force: false,
    help: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") {
      args.help = true;
    } else if (arg === "--agent") {
      args.agent = requiredValue(argv, ++index, arg);
    } else if (arg === "--scope") {
      args.scope = requiredValue(argv, ++index, arg);
    } else if (arg === "--project") {
      args.project = requiredValue(argv, ++index, arg);
    } else if (arg === "--dry-run") {
      args.dryRun = true;
    } else if (arg === "--force") {
      args.force = true;
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  return args;
}

function requiredValue(argv, index, flag) {
  if (index >= argv.length || argv[index].startsWith("--")) {
    throw new Error(`${flag} requires a value`);
  }
  return argv[index];
}

function copyRecursive(from, to) {
  const stat = fs.lstatSync(from);
  if (stat.isDirectory()) {
    fs.mkdirSync(to, { recursive: true });
    for (const entry of fs.readdirSync(from)) {
      if (entry.startsWith(".")) {
        continue;
      }
      copyRecursive(path.join(from, entry), path.join(to, entry));
    }
    return;
  }
  fs.copyFileSync(from, to);
}

function removeDir(target) {
  if (!fs.existsSync(target)) {
    return;
  }
  for (const entry of fs.readdirSync(target)) {
    const full = path.join(target, entry);
    const stat = fs.lstatSync(full);
    if (stat.isDirectory()) {
      removeDir(full);
    } else {
      fs.unlinkSync(full);
    }
  }
  fs.rmdirSync(target);
}

function printHelp() {
  console.log(`Usage: flowtrim-skill-install --agent <claude|codex|copilot> [--scope user|project] [--project PATH] [--dry-run] [--force]

Examples:
  npx github:ozifer33/flowtrim --agent codex --scope user
  npx github:ozifer33/flowtrim --agent claude --scope project --project .
  npx github:ozifer33/flowtrim --agent copilot --scope project --project .`);
}

try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
