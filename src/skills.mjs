import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// 拷贝/打包 skill 时跳过的目录与文件（对齐 .gitignore，避免把本地产物装进目标）
const EXCLUDE_NAMES = new Set([".venv", "venv", "__pycache__", "node_modules", ".git", ".DS_Store"]);

export function findRepoRoot() {
  // src/skills.mjs 位于 <repo>/src/ 下，仓库根即上一级
  return path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
}

// 仓库内 skill 的存放位置：resources/skill/<skill-name>/SKILL.md（兼容一层分类子目录）
export function skillsDir() {
  return path.join(findRepoRoot(), "resources", "skill");
}

export function parseFrontmatter(text) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text);
  if (!m) return {};
  const fm = {};
  for (const line of m[1].split(/\r?\n/)) {
    const kv = /^(\w[\w-]*):\s*(.*)$/.exec(line);
    if (!kv) continue;
    fm[kv[1]] = kv[2].replace(/^["']|["']$/g, "").trim();
  }
  return fm;
}

function makeSkill(category, id, dir) {
  const skillMd = path.join(dir, "SKILL.md");
  let fm = {};
  try {
    fm = parseFrontmatter(fs.readFileSync(skillMd, "utf8"));
  } catch {
    // SKILL.md 不可读时仍列出该目录，只是没有描述
  }
  return {
    category,
    id,
    name: fm.name || id,
    description: fm.description || "",
    dir,
    skillMd,
  };
}

// 发现仓库内全部 skill：skillsDir 下（含二级目录）任何带 SKILL.md 的目录
export function discoverSkills(root = skillsDir()) {
  const skills = [];
  const seen = new Set();
  const push = (s) => {
    if (seen.has(s.id)) throw new Error(`skill 目录名冲突：${s.id}（${s.dir}）`);
    seen.add(s.id);
    skills.push(s);
  };
  for (const top of listDirs(root)) {
    const topDir = path.join(root, top);
    if (fs.existsSync(path.join(topDir, "SKILL.md"))) {
      // 直接位于根下的 skill（扁平布局）：category 用根目录名
      push(makeSkill(path.basename(root), top, topDir));
    }
    for (const sub of listDirs(topDir)) {
      const subDir = path.join(topDir, sub);
      if (fs.existsSync(path.join(subDir, "SKILL.md"))) {
        push(makeSkill(top, sub, subDir));
      }
    }
  }
  return skills;
}

function listDirs(dir) {
  try {
    return fs
      .readdirSync(dir, { withFileTypes: true })
      .filter((e) => e.isDirectory() && !e.name.startsWith("."))
      .map((e) => e.name)
      .sort();
  } catch {
    return [];
  }
}

export function copyDir(src, dest) {
  fs.cpSync(src, dest, {
    recursive: true,
    filter: (s) => s === src || !EXCLUDE_NAMES.has(path.basename(s)),
  });
}
