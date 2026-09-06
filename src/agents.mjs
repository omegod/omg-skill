import os from "node:os";
import path from "node:path";

const home = os.homedir();
const env = (k, fallback) => process.env[k] || fallback;
const P = path.join;

// 各 agent 的 skills 目录约定（用户级经本机验证；cursor 用户级路径官方文档未明确，注明存疑）
export const AGENTS = [
  {
    id: "claude-code",
    label: "Claude Code",
    user: () => P(home, ".claude", "skills"),
    project: ".claude/skills",
  },
  {
    id: "codex",
    label: "Codex CLI",
    user: () => P(env("CODEX_HOME", P(home, ".codex")), "skills"),
    project: ".codex/skills",
  },
  {
    id: "zcode",
    label: "ZCode",
    user: () => P(home, ".zcode", "skills"),
    project: ".zcode/skills",
  },
  {
    id: "opencode",
    label: "opencode",
    user: () => P(env("XDG_CONFIG_HOME", P(home, ".config")), "opencode", "skills"),
    project: ".opencode/skills",
  },
  {
    id: "cursor",
    label: "Cursor",
    user: () => P(home, ".cursor", "skills"),
    project: ".cursor/skills",
    note: "用户级路径未经官方文档确认",
  },
  {
    id: "agents",
    label: "通用 agents",
    user: () => P(home, ".agents", "skills"),
    project: ".agents/skills",
    note: "跨工具共享目录",
  },
];

export function getAgent(id) {
  const a = AGENTS.find((a) => a.id === id);
  if (!a) {
    throw new Error(`未知 agent：${id}（可选：${AGENTS.map((a) => a.id).join(", ")}）`);
  }
  return a;
}

// 项目级安装基准目录：默认当前工作目录，可被 --dir 覆盖
export function projectBase(dirFlag) {
  return path.resolve(dirFlag || process.cwd());
}
