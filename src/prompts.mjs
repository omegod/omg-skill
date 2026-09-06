import readline from "node:readline";
import process from "node:process";

// 零依赖交互原语：raw mode + keypress + ANSI 重绘。
// 仅支持方向键/空格/回车等基础键位，足够多选 skill 与 agent 使用。

const useColor = process.stdout.isTTY && !process.env.NO_COLOR;
const c = (code, s) => (useColor ? `\x1b[${code}m${s}\x1b[0m` : String(s));
export const dim = (s) => c("2", s);
export const bold = (s) => c("1", s);
export const cyan = (s) => c("36", s);
export const green = (s) => c("32", s);
export const red = (s) => c("31", s);
export const yellow = (s) => c("33", s);

export class PromptAborted extends Error {
  constructor() {
    super("用户取消");
    this.aborted = true;
  }
}

// ---- 显示宽度工具：CJK/全角/emoji 占 2 列，截断与裁剪必须按列数而非字符数，
// 否则长中文行在终端换行，破坏"光标上移重绘"的行数对位，导致画面堆积。
function isWide(cp) {
  return (
    (cp >= 0x1100 && cp <= 0x115f) ||
    (cp >= 0x2e80 && cp <= 0xa4cf) ||
    (cp >= 0xac00 && cp <= 0xd7a3) ||
    (cp >= 0xf900 && cp <= 0xfaff) ||
    (cp >= 0xfe30 && cp <= 0xfe4f) ||
    (cp >= 0xff00 && cp <= 0xff60) ||
    (cp >= 0xffe0 && cp <= 0xffe6) ||
    (cp >= 0x1f300 && cp <= 0x1faff) ||
    (cp >= 0x20000 && cp <= 0x3fffd)
  );
}

const ANSI_RE = /\x1b\[[0-9;]*[A-Za-z]/g;

export function displayWidth(s) {
  let w = 0;
  for (const ch of s.replace(ANSI_RE, "")) w += isWide(ch.codePointAt(0)) ? 2 : 1;
  return w;
}

// 按显示宽度截断，超宽时以 …（1 列）结尾；ANSI 序列保留且不计宽
export function truncateWidth(s, maxCols) {
  if (displayWidth(s) <= maxCols) return s;
  let w = 0;
  let out = "";
  let i = 0;
  while (i < s.length) {
    if (s[i] === "\x1b") {
      const m = /^\x1b\[[0-9;]*[A-Za-z]/.exec(s.slice(i));
      if (m) {
        out += m[0];
        i += m[0].length;
        continue;
      }
    }
    const ch = String.fromCodePoint(s.codePointAt(i));
    const cw = isWide(ch.codePointAt(0)) ? 2 : 1;
    if (w + cw > maxCols - 1) break;
    out += ch;
    w += cw;
    i += ch.length;
  }
  if (s.includes("\x1b")) out += "\x1b[0m"; // 截断可能丢掉闭合的颜色序列
  return out + "…";
}

// 逐字符裁剪到 maxCols 列；ANSI 转义序列原样保留、不计宽度
function clipAnsi(s, maxCols) {
  let out = "";
  let w = 0;
  let i = 0;
  let truncated = false;
  while (i < s.length) {
    if (s[i] === "\x1b") {
      const m = /^\x1b\[[0-9;]*[A-Za-z]/.exec(s.slice(i));
      if (m) {
        out += m[0];
        i += m[0].length;
        continue;
      }
    }
    const ch = String.fromCodePoint(s.codePointAt(i));
    const cw = isWide(ch.codePointAt(0)) ? 2 : 1;
    if (w + cw > maxCols) {
      truncated = true;
      break;
    }
    out += ch;
    w += cw;
    i += ch.length;
  }
  if (truncated && useColor) out += "\x1b[0m"; // 截断点可能落在颜色序列中间
  return out;
}

// 选项行 hint 自适应：按终端宽度与 label 实际列宽预算可用空间（❯ ◉ + 间距 + 余量 ≈ 14 列）
function fitHint(hint, label) {
  const cols = Math.max(process.stdout.columns || 80, 40);
  const budget = Math.max(cols - 14 - displayWidth(label), 8);
  return truncateWidth(hint, budget);
}

function assertTTY() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    throw new Error("需要交互终端（TTY）；在脚本中使用 --agent/--skill/--global/--local 等参数");
  }
}

const KEY_DEBUG = process.env.CU_KEY_DEBUG; // 调试用：CU_KEY_DEBUG=1 打印按键事件
const klog = (tag, msg) => {
  if (KEY_DEBUG) console.error(`[kd ${String(Date.now()).slice(-6)} ${tag}] ${msg}`);
};

class KeyReader {
  constructor(tag) {
    this.tag = tag;
    readline.emitKeypressEvents(process.stdin);
    process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.ref?.(); // 等待按键期间保持事件循环存活
    this.queue = [];
    this.resolvers = [];
    klog(tag, "start");
    this.onKey = (str, key) => {
      klog(tag, `key ${JSON.stringify(str)} name=${key && key.name}`);
      const k = { str: str || "", key: key || {} };
      if (this.resolvers.length) this.resolvers.shift()(k);
      else this.queue.push(k);
    };
    process.stdin.on("keypress", this.onKey);
  }
  next() {
    return this.queue.length
      ? Promise.resolve(this.queue.shift())
      : new Promise((r) => this.resolvers.push(r));
  }
  end() {
    klog(this.tag, "end");
    process.stdin.removeListener("keypress", this.onKey);
    if (process.stdin.isTTY) process.stdin.setRawMode(false);
    process.stdin.pause();
    // 解除引用，否则所有提示结束后事件循环不退出，CLI 会挂住
    process.stdin.unref?.();
  }
}

class Renderer {
  constructor() {
    this.prev = 0;
    this.wrapOff = false;
  }
  draw(lines) {
    // 列数留 1 列余量；绘制期间关闭自动换行，确保帧行数恒等、重绘对位准确
    const cols = Math.max((process.stdout.columns || 80) - 1, 20);
    const out = [];
    if (this.prev > 0) out.push(`\x1b[${this.prev}A`);
    else {
      out.push("\x1b[?7l");
      this.wrapOff = true;
    }
    for (const line of lines) out.push(`\r\x1b[2K${clipAnsi(line, cols)}\n`);
    out.push("\x1b[J"); // 新帧更短时清掉残留行
    process.stdout.write(out.join(""));
    this.prev = lines.length;
  }
  clear() {
    if (this.prev > 0) process.stdout.write(`\x1b[${this.prev}A`);
    process.stdout.write("\r\x1b[J");
    if (this.wrapOff) {
      process.stdout.write("\x1b[?7h"); // 恢复自动换行，后续普通输出不受影响
      this.wrapOff = false;
    }
    this.prev = 0;
  }
}

const isEnter = (k) => k.key.name === "return" || k.key.name === "enter";
const isCtrlC = (k) => k.key.ctrl && k.key.name === "c";

export async function select(message, options, { initial = 0, hint } = {}) {
  assertTTY();
  const kr = new KeyReader();
  const r = new Renderer();
  let i = Math.min(Math.max(initial, 0), options.length - 1);
  try {
    while (true) {
      const lines = [`${cyan("◆")} ${bold(message)}`];
      if (hint) lines.push(dim(hint));
      options.forEach((o, idx) => {
        const active = idx === i;
        const pointer = active ? cyan("❯") : " ";
        const mark = active ? cyan("●") : dim("○");
        const label = active ? bold(o.label) : o.label;
        const h = active && o.hint ? dim(`  ${fitHint(o.hint, o.label)}`) : "";
        lines.push(`${pointer} ${mark} ${label}${h}`);
      });
      lines.push(dim("↑/↓ 移动 · Enter 确认 · Ctrl+C 取消"));
      r.draw(lines);
      const k = await kr.next();
      if (isCtrlC(k)) throw new PromptAborted();
      if (k.key.name === "up" || k.str === "k") i = (i - 1 + options.length) % options.length;
      if (k.key.name === "down" || k.str === "j") i = (i + 1) % options.length;
      if (isEnter(k)) {
        r.clear();
        console.log(`${green("✔")} ${message} ${cyan(options[i].label)}`);
        return options[i].value;
      }
    }
  } catch (e) {
    r.clear();
    throw e;
  } finally {
    kr.end();
  }
}

export async function multiselect(message, options, { initial = [], min = 1, hint } = {}) {
  assertTTY();
  const kr = new KeyReader();
  const r = new Renderer();
  const selected = new Set(initial.filter((v) => options.some((o) => o.value === v)));
  let i = 0;
  let error = "";
  try {
    while (true) {
      const lines = [`${cyan("◆")} ${bold(message)}`];
      if (hint) lines.push(dim(hint));
      lines.push(dim(`已选 ${selected.size}/${options.length}（空格 勾选 · a 全选/反全选）`));
      options.forEach((o, idx) => {
        const active = idx === i;
        const pointer = active ? cyan("❯") : " ";
        const mark = selected.has(o.value) ? green("◉") : dim("○");
        const label = active ? bold(o.label) : o.label;
        const h = active && o.hint ? dim(`  ${fitHint(o.hint, o.label)}`) : "";
        lines.push(`${pointer} ${mark} ${label}${h}`);
      });
      lines.push(error ? red(`✖ ${error}`) : dim("Enter 确认 · Ctrl+C 取消"));
      r.draw(lines);
      const k = await kr.next();
      if (isCtrlC(k)) throw new PromptAborted();
      error = "";
      if (k.key.name === "up" || k.str === "k") i = (i - 1 + options.length) % options.length;
      if (k.key.name === "down" || k.str === "j") i = (i + 1) % options.length;
      if (k.str === " ") {
        const v = options[i].value;
        selected.has(v) ? selected.delete(v) : selected.add(v);
      }
      if (k.str === "a") {
        if (selected.size === options.length) selected.clear();
        else options.forEach((o) => selected.add(o.value));
      }
      if (isEnter(k)) {
        if (selected.size < min) {
          error = `至少需要选择 ${min} 项`;
          continue;
        }
        r.clear();
        const picked = options.filter((o) => selected.has(o.value));
        console.log(
          `${green("✔")} ${message} ${cyan(picked.map((o) => o.label).join(", ") || "无")}`
        );
        return picked.map((o) => o.value);
      }
    }
  } catch (e) {
    r.clear();
    throw e;
  } finally {
    kr.end();
  }
}

export async function confirm(message, { initial = true } = {}) {
  assertTTY();
  const kr = new KeyReader();
  const r = new Renderer();
  let yes = initial;
  try {
    while (true) {
      const lines = [
        `${cyan("◆")} ${bold(message)}`,
        `  ${yes ? bold(green("是")) : dim("是")} / ${!yes ? bold(red("否")) : dim("否")}`,
        dim("←/→ 或 y/n 切换 · Enter 确认 · Ctrl+C 取消"),
      ];
      r.draw(lines);
      const k = await kr.next();
      if (isCtrlC(k)) throw new PromptAborted();
      if (k.str === "y") yes = true;
      if (k.str === "n") yes = false;
      if (k.key.name === "left" || k.key.name === "right") yes = !yes;
      if (isEnter(k)) {
        r.clear();
        console.log(`${green("✔")} ${message} ${yes ? cyan("是") : cyan("否")}`);
        return yes;
      }
    }
  } catch (e) {
    r.clear();
    throw e;
  } finally {
    kr.end();
  }
}

export async function text(message, { initial = "", placeholder = "" } = {}) {
  assertTTY();
  const kr = new KeyReader();
  const r = new Renderer();
  let buf = initial;
  try {
    while (true) {
      const shown = buf || dim(placeholder);
      const lines = [
        `${cyan("◆")} ${bold(message)}`,
        `  ${cyan("›")} ${shown}${buf ? dim("▏") : ""}`,
        dim("Enter 确认" + (placeholder ? "（留空使用默认）" : "") + " · Ctrl+C 取消"),
      ];
      r.draw(lines);
      const k = await kr.next();
      if (isCtrlC(k)) throw new PromptAborted();
      if (isEnter(k)) {
        const value = buf || placeholder;
        r.clear();
        console.log(`${green("✔")} ${message} ${cyan(value || "(空)")}`);
        return value;
      }
      if (k.key.name === "backspace" || k.key.name === "delete") buf = buf.slice(0, -1);
      else if (!k.key.ctrl && !k.key.meta && k.str) buf += k.str;
    }
  } catch (e) {
    r.clear();
    throw e;
  } finally {
    kr.end();
  }
}
