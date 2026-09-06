import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { copyDir } from "./skills.mjs";
import { confirm, green, red, dim, yellow } from "./prompts.mjs";

const home = os.homedir();
const tilde = (p) => (p.startsWith(home) ? p.slice(home.length).replace(/^\//, "~/") : p);

// scope: "user" → agent 用户级目录；"local" → baseDir/<agent project>/
export function buildTargets({ skills, agents, scope, baseDir }) {
  const targets = [];
  for (const a of agents) {
    const base = scope === "user" ? a.user() : path.join(baseDir, a.project);
    for (const s of skills) {
      targets.push({ agent: a, skill: s, base, target: path.join(base, s.id) });
    }
  }
  return targets;
}

export async function executeInstall(targets, { yes = false, dryRun = false } = {}) {
  const results = [];
  for (const t of targets) {
    const exists = fs.existsSync(t.target);
    if (exists && !yes && !dryRun) {
      const overwrite = await confirm(`目标已存在，覆盖？ ${dim(tilde(t.target))}`, {
        initial: true,
      });
      if (!overwrite) {
        results.push({ ...t, status: "skipped" });
        continue;
      }
    }
    if (dryRun) {
      results.push({ ...t, status: exists ? "will-overwrite" : "will-install" });
      continue;
    }
    try {
      fs.mkdirSync(t.base, { recursive: true });
      copyDir(t.skill.dir, t.target);
      results.push({ ...t, status: exists ? "overwritten" : "installed" });
    } catch (e) {
      results.push({ ...t, status: "failed", error: e.message });
    }
  }
  return results;
}

export async function executeUninstall(targets, { yes = false, dryRun = false } = {}) {
  const results = [];
  for (const t of targets) {
    if (!fs.existsSync(t.target)) {
      results.push({ ...t, status: "missing" });
      continue;
    }
    if (!yes && !dryRun) {
      const ok = await confirm(`删除目录？ ${dim(tilde(t.target))}`, { initial: true });
      if (!ok) {
        results.push({ ...t, status: "skipped" });
        continue;
      }
    }
    if (dryRun) {
      results.push({ ...t, status: "will-remove" });
      continue;
    }
    try {
      fs.rmSync(t.target, { recursive: true, force: true });
      results.push({ ...t, status: "removed" });
    } catch (e) {
      results.push({ ...t, status: "failed", error: e.message });
    }
  }
  return results;
}

const STATUS_TEXT = {
  installed: ["✔", green, "已安装"],
  overwritten: ["✔", green, "已覆盖"],
  removed: ["✔", green, "已删除"],
  "will-install": ["·", dim, "将安装"],
  "will-overwrite": ["·", yellow, "将覆盖（已存在）"],
  "will-remove": ["·", yellow, "将删除（已存在）"],
  skipped: ["-", dim, "已跳过"],
  missing: ["-", dim, "未安装，跳过"],
  conflict: ["!", yellow, "目标已存在（--yes 可强制覆盖）"],
  failed: ["✖", red, "失败"],
};

export function printResults(results, { label = "完成" } = {}) {
  for (const r of results) {
    const [mark, color, text] = STATUS_TEXT[r.status] || ["?", dim, r.status];
    const detail = r.error ? `（${r.error}）` : "";
    console.log(`  ${color(mark)} ${color(text)}  ${dim(r.agent.label)}  ${tilde(r.target)}${detail}`);
  }
  const failed = results.filter((r) => r.status === "failed").length;
  const tail = failed
    ? `，失败 ${failed}`
    : label.startsWith("dry-run")
      ? "，计划就绪"
      : "，全部成功 🎉";
  console.log(dim(`\n  ${label}：共 ${results.length} 项${tail}`));
}
