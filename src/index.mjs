#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import { AGENTS, getAgent, projectBase } from "./agents.mjs";
import { discoverSkills } from "./skills.mjs";
import {
  select,
  multiselect,
  confirm,
  text,
  PromptAborted,
  truncateWidth,
  dim,
  bold,
  cyan,
  green,
  red,
  yellow,
} from "./prompts.mjs";
import { buildTargets, executeInstall, executeUninstall, printResults } from "./install.mjs";

const VERSION = JSON.parse(
  fs.readFileSync(new URL("../package.json", import.meta.url), "utf8")
).version;
const HOME = os.homedir();

const USAGE = `omg-skill v${VERSION} —— 把本仓库的 skill 安装到各 AI agent 的 skills 目录

用法：omg-skill [command] [options]

命令：
  install                    安装 skill（默认命令，无参数时进入交互模式）
  list                       列出仓库内的 skill 与支持的 agent
  uninstall                  从 agent 的 skills 目录移除 skill

选项：
  -a, --agent <id,id>        目标 agent，逗号分隔：
                             claude-code, codex, zcode, opencode, cursor, agents
  -s, --skill <id,id>        要安装的 skill（目录名），逗号分隔
  -g, --global               用户级安装（~/.claude/skills 等，全局可用）
  -l, --local                项目级安装（<目录>/.claude/skills 等，仅该项目可用）
      --dir <path>           项目级安装基准目录（默认：当前目录）
  -y, --yes                  跳过确认，覆盖已存在的目标
      --dry-run              只打印安装计划，不写入任何文件
  -h, --help                 显示本帮助
  -v, --version              显示版本

示例：
  node src/index.mjs                                    # 交互式选择 skill、agent、范围
  node src/index.mjs install -a claude-code,codex -s computer-use,image-describe -g -y
  node src/index.mjs install -a cursor -s image-describe -l --dir ~/my-project
  node src/index.mjs uninstall -a claude-code -s computer-use -g -y`;

function usage() {
  console.log(USAGE);
}

function parseArgs(argv) {
  const flags = {
    command: "install",
    agents: [],
    skills: [],
    scope: null,
    dir: null,
    yes: false,
    dryRun: false,
    help: false,
    version: false,
  };
  const csv = (v) =>
    v
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) throw new Error(`选项 ${arg} 缺少值`);
      return argv[++i];
    };
    switch (arg) {
      case "install":
      case "list":
      case "uninstall":
      case "help":
        flags.command = arg;
        break;
      case "-a":
      case "--agent":
        flags.agents.push(...csv(next()));
        break;
      case "-s":
      case "--skill":
      case "--skills":
        flags.skills.push(...csv(next()));
        break;
      case "-g":
      case "--global":
        flags.scope = "user";
        break;
      case "-l":
      case "--local":
        flags.scope = "local";
        break;
      case "--dir":
        flags.dir = next();
        break;
      case "-y":
      case "--yes":
        flags.yes = true;
        break;
      case "--dry-run":
        flags.dryRun = true;
        break;
      case "-h":
      case "--help":
        flags.help = true;
        break;
      case "-v":
      case "--version":
        flags.version = true;
        break;
      default:
        if (arg.startsWith("-")) throw new Error(`未知选项：${arg}（--help 查看用法）`);
        rest.push(arg);
    }
  }
  if (rest.length) flags.command = rest[0];
  return flags;
}

const isInteractive = () => Boolean(process.stdin.isTTY && process.stdout.isTTY);
const tilde = (p) => (p.startsWith(HOME) ? p.slice(HOME.length).replace(/^\//, "~/") : p);

function matchSkills(all, ids) {
  const out = [];
  const missing = [];
  for (const id of ids) {
    const s = all.find((x) => x.id === id || x.name === id);
    if (s) out.push(s);
    else missing.push(id);
  }
  if (missing.length) {
    throw new Error(
      `未找到 skill：${missing.join(", ")}（可用：${all.map((s) => s.id).join(", ")}）`
    );
  }
  return out;
}

function matchAgents(ids) {
  const seen = new Set();
  return ids.map((id) => {
    if (seen.has(id)) return null;
    seen.add(id);
    return getAgent(id);
  }).filter(Boolean);
}

function printTargets(title, targets) {
  console.log(bold(title));
  for (const t of targets) console.log(`  ${dim("·")} ${dim(t.agent.label)}  ${tilde(t.target)}`);
}

async function resolveScope(flags) {
  if (flags.scope) {
    if (flags.scope === "user" && flags.dir) {
      throw new Error("--dir 只用于项目级安装（--local），与 --global 冲突");
    }
    return flags.scope;
  }
  if (!isInteractive()) throw new Error("缺少安装范围：请加 --global 或 --local（--help 查看用法）");
  const scope = await select("安装到哪里？", [
    { value: "user", label: "用户级", hint: "安装到 ~/.claude/skills 等，所有项目可用（推荐）" },
    { value: "local", label: "项目级", hint: "安装到当前项目 .claude/skills 等，仅该项目可用" },
  ]);
  return scope;
}

// 项目级安装的基准目录：--dir 优先，其次交互输入，非交互时用当前目录
async function resolveLocalBase(flags, scope) {
  if (scope !== "local") return null;
  if (flags.dir || !isInteractive() || flags.yes) return projectBase(flags.dir);
  const dir = await text("项目级安装基准目录", { placeholder: process.cwd() });
  return projectBase(dir || process.cwd());
}

async function runInstall(flags) {
  const allSkills = discoverSkills();
  let skills = flags.skills.length ? matchSkills(allSkills, flags.skills) : [];
  let agents = flags.agents.length ? matchAgents(flags.agents) : [];

  if (!skills.length) {
    if (!isInteractive()) throw new Error("缺少 --skill 参数（--help 查看用法）");
    const ids = await multiselect("选择要安装的 skill", allSkills.map(s => ({
      value: s.id,
      label: s.name,
      hint: s.description,
    })), { min: 1 });
    skills = matchSkills(allSkills, ids);
  }
  if (!agents.length) {
    if (!isInteractive()) throw new Error("缺少 --agent 参数（--help 查看用法）");
    const ids = await multiselect("安装到哪些 agent？", AGENTS.map(a => ({
      value: a.id,
      label: a.label + (a.note ? dim(`（${a.note}）`) : ""),
      hint: tilde(a.user()),
    })), { min: 1 });
    agents = matchAgents(ids);
  }

  const scope = await resolveScope(flags);
  const baseDir = await resolveLocalBase(flags, scope);

  const targets = buildTargets({ skills, agents, scope, baseDir });
  if (!targets.length) throw new Error("没有可安装的目标");

  if (flags.dryRun) {
    const results = await executeInstall(targets, { yes: flags.yes, dryRun: true });
    printResults(results, { label: "dry-run 安装计划（未写入任何文件）" });
    return;
  }
  if (!flags.yes && isInteractive()) {
    printTargets(`将安装 ${skills.length} 个 skill × ${agents.length} 个 agent（${scope === "user" ? "用户级" : "项目级 " + tilde(baseDir)}）：`, targets);
    if (!(await confirm("开始安装？", { initial: true }))) {
      console.log(dim("已取消"));
      return;
    }
  }
  const results = await executeInstall(targets, { yes: flags.yes, dryRun: false });
  printResults(results);
}

function installedSkillsIn(base) {
  try {
    return new Set(
      fs.readdirSync(base, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name)
    );
  } catch {
    return new Set();
  }
}

function cmdList() {
  const skills = discoverSkills();
  console.log(bold(`仓库内的 skill（${skills.length} 个）`));
  for (const s of skills) {
    console.log(`  ${cyan(s.id)}  ${dim(truncateWidth(s.description, 76))}`);
  }
  console.log(`\n${bold(`支持的 agent（${AGENTS.length} 个）`)}`);
  const installed = new Set(skills.map((s) => s.id));
  for (const a of AGENTS) {
    const dirs = installedSkillsIn(a.user());
    const hit = [...installed].filter((id) => dirs.has(id));
    const tag = hit.length ? green(`已装: ${hit.join(", ")}`) : dim("未安装本仓库 skill");
    console.log(
      `  ${cyan(a.id.padEnd(12))} ${dim("用户级")} ${tilde(a.user())}  ${tag}` +
        (a.note ? dim(`（${a.note}）`) : "")
    );
    console.log(`  ${" ".repeat(12)} ${dim("项目级")} ./${a.project}`);
  }
}

async function runUninstall(flags) {
  const allSkills = discoverSkills();
  let agents = flags.agents.length ? matchAgents(flags.agents) : [];
  if (!agents.length) {
    if (!isInteractive()) throw new Error("缺少 --agent 参数（--help 查看用法）");
    const ids = await multiselect("从哪些 agent 移除？", AGENTS.map(a => ({
      value: a.id,
      label: a.label,
      hint: tilde(a.user()),
    })), { min: 1 });
    agents = matchAgents(ids);
  }
  const scope = await resolveScope(flags);
  const baseDir = await resolveLocalBase(flags, scope);

  let targets = buildTargets({ skills: allSkills, agents, scope, baseDir }).filter(
    (t) => fs.existsSync(t.target)
  );
  if (!targets.length) {
    console.log(yellow("这些 agent 的 skills 目录里没有本仓库的 skill，无需卸载"));
    return;
  }

  let skills;
  if (flags.skills.length) {
    skills = matchSkills(allSkills, flags.skills);
    targets = targets.filter((t) => skills.some((s) => s.id === t.skill.id));
    if (!targets.length) {
      console.log(yellow("指定的 skill 未安装在所选 agent 中，无需卸载"));
      return;
    }
  } else {
    if (!isInteractive()) throw new Error("缺少 --skill 参数（--help 查看用法）");
    const uniqueSkills = [...new Map(targets.map((t) => [t.skill.id, t.skill])).values()];
    const ids = await multiselect("选择要移除的 skill", uniqueSkills.map(s => ({
      value: s.id,
      label: s.name,
      hint: s.description,
    })), { min: 1, initial: uniqueSkills.map((s) => s.id) });
    targets = targets.filter((t) => ids.includes(t.skill.id));
  }

  if (flags.dryRun) {
    const results = await executeUninstall(targets, { yes: flags.yes, dryRun: true });
    printResults(results, { label: "dry-run 卸载计划（未删除任何文件）" });
    return;
  }
  if (!flags.yes && isInteractive()) {
    printTargets(`将删除以下目录：`, targets);
    if (!(await confirm("确认删除？", { initial: false }))) {
      console.log(dim("已取消"));
      return;
    }
  }
  const results = await executeUninstall(targets, { yes: flags.yes });
  printResults(results);
}

async function main() {
  const flags = parseArgs(process.argv.slice(2));
  if (flags.version) return console.log(VERSION);
  if (flags.help || flags.command === "help") return usage();
  if (flags.command === "list") return cmdList();
  if (flags.command === "uninstall") return runUninstall(flags);
  return runInstall(flags);
}

try {
  await main();
} catch (e) {
  if (e instanceof PromptAborted) {
    console.log(dim("\n已取消"));
    process.exit(130);
  }
  console.error(`${red("✖")} ${e.message}`);
  process.exit(1);
}
