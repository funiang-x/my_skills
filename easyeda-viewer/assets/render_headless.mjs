// render_headless.mjs — easyeda-viewer 无头渲染自检
// 由 skill `easyeda-viewer` 的 scripts/viewer.py render 调用：
//   1) 复制到 <viewer>/.bridge-work/skill/（vite-node 的 fs 白名单要求脚本在仓库内）
//   2) 在 viewer 仓库根目录执行：
//      node node_modules/vite-node/vite-node.mjs -c vite.smoke.config.ts .bridge-work/skill/render_headless.mjs <file...>
//
// 输出：每文件一行  OK  <name>  fmt=..  doc=..  obj=..  layers=..  unknown=..
// 判据：unknown=0 且 obj 数与预期相符 = 源码被完全理解且确有内容。
globalThis.CanvasRenderingContext2D = class {};
globalThis.Path2D = class {};
globalThis.OffscreenCanvas = class { getContext() { return {}; } };
globalThis.Image = class {};
globalThis.HTMLCanvasElement = class {};
globalThis.document = {
  createElement: () => ({ style: {}, classList: { add() {} }, getContext: () => ({}), appendChild() {} }),
  body: { appendChild() {} },
};
globalThis.window = globalThis;

const { readFileSync } = await import('node:fs');
const path = await import('node:path');
const os = await import('node:os');
const REPO = process.env.EASYEDA_VIEWER_DIR || path.join(os.homedir(), 'easyeda-viewer');
const { loadFromMap } = await import(REPO + '/src/core/parse/container.ts');
const { openDoc } = await import(REPO + '/src/core/model.ts');
const { renderDoc } = await import(REPO + '/src/core/render/layers.ts');

let bad = 0;
for (const file of process.argv.slice(2)) {
  const map = new Map([[path.basename(file), new Uint8Array(readFileSync(file))]]);
  try {
    const m = loadFromMap(map);
    for (const n of m.openables.values()) {
      const r = renderDoc(openDoc(m, n));
      const unk = r.report.unknownTypes.length;
      if (unk) bad++;
      console.log('OK  ' + path.basename(file) + '  fmt=' + m.format + '  doc=' + n.docType +
        '  obj=' + r.objects.length + '  layers=' + r.layers.length + '  unknown=' + unk);
    }
  } catch (e) {
    bad++;
    console.log('ERR ' + path.basename(file) + ': ' + String(e.stack || e).split('\n').slice(0, 3).join(' | '));
  }
}
process.exit(bad ? 1 : 0);
