// shot_doc.mjs — 打开工程包(.epro2) → 点选文档树里的指定页 → 按文档坐标放大 → 截图
// 这是 AI 的"眼睛·完整版"：单页 .esch2 没有符号库（渲染成虚线占位框），
// 要看真正的图纸必须喂工程包 .epro2（见 LESSONS.md T-54）。
//
// 用法（cwd = viewer 仓库根，node_modules 里有 puppeteer-core）：
//   node .bridge-work/skill/shot_doc.mjs <url> <out.png> <docName> [w] [h] [waitMs] [zoomX] [zoomY] [zoomTimes]
//   - docName   文档树里页名的一部分（如 "AFE"）；空串则不动树
//   - zoomX/Y   放大中心点的**文档坐标**（与原理图元件 x/y 同一坐标系，y 向上）
//   - zoomTimes 滚轮次数：每次 ×1.82（pow(1.0015, 400)），0 = 不放大（整页 fit）
// 实现要点（踩过的坑）：
//   - 直接改 window.__ev.shell.camera.scale/centerOn 会被 viewer 的 fit 重置；
//     有效做法 = 读 camera 的 tx/ty/scale 算出目标点的**屏幕坐标**，在该点派发 wheel 事件
//   - camera 的世界坐标 y 与文档记录同号（记录里 y 取负），故 screen_y = ty + (-docY) * scale
//   - 截图裁到 canvas 区域（chrome=canvas 下即整块画布）
import puppeteer from 'puppeteer-core';
import { existsSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const CHROME = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync);
if (!CHROME) { console.log('ERR no chrome'); process.exit(1); }

const url = process.argv[2];
const out = process.argv[3];
const docName = process.argv[4] || '';
const W = Number(process.argv[5] || 1800);
const H = Number(process.argv[6] || 1000);
const WAIT = Number(process.argv[7] || 12000);
const ZX = Number(process.argv[8] || 'NaN');
const ZY = Number(process.argv[9] || 'NaN');
const ZT = Number(process.argv[10] || 0);

mkdirSync(dirname(resolve(out)), { recursive: true });
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => console.log('PAGEERR', String(e.message).slice(0, 160)));
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });

  const fr = page.frames().find((f) => f.url().includes('viewer.html'));
  if (!fr) throw new Error('viewer iframe not found');
  await fr.waitForSelector('.ev-tree-row', { timeout: 40000 });
  await new Promise((r) => setTimeout(r, 2500));

  if (docName) {
    const clicked = await fr.evaluate((name) => {
      const rows = [...document.querySelectorAll('.ev-tree-row')];
      const hit = rows.find((r) => (r.textContent || '').includes(name));
      if (!hit) return false;
      hit.click();
      return true;
    }, docName);
    console.log('click "' + docName + '": ' + clicked);
    await new Promise((r) => setTimeout(r, Math.max(3500, WAIT - 4500)));
  } else {
    await new Promise((r) => setTimeout(r, WAIT));
  }

  if (ZT > 0 && !Number.isNaN(ZX) && !Number.isNaN(ZY)) {
    const info = await fr.evaluate((dx, dy, times) => {
      const cam = window.__ev && window.__ev.shell && window.__ev.shell.camera;
      if (!cam) return { err: 'no camera' };
      const px = cam.tx + dx * cam.scale;
      const py = cam.ty + (-dy) * cam.scale;
      const out = { px: px, py: py, scale0: cam.scale };
      const cv = document.querySelector('.ev-canvas') || document.querySelector('canvas');
      const rect = cv.getBoundingClientRect();
      out.inside = px >= 0 && px <= rect.width && py >= 0 && py <= rect.height;
      for (let i = 0; i < times; i++) {
        cv.dispatchEvent(new WheelEvent('wheel',
          { deltaY: -400, clientX: px, clientY: py, bubbles: true, cancelable: true }));
      }
      out.scale1 = cam.scale;
      return out;
    }, ZX, ZY, Math.max(1, Math.round(ZT)));
    console.log('zoom: ' + JSON.stringify(info));
    await new Promise((r) => setTimeout(r, 1500));
  }

  const canvasBox = await fr.evaluate(() => {
    const c = document.querySelector('canvas');
    if (!c) return null;
    const r = c.getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  });
  if (canvasBox && canvasBox.width > 200 && canvasBox.height > 200) {
    await page.screenshot({ path: resolve(out), clip: canvasBox });
  } else {
    await page.screenshot({ path: resolve(out) });
  }
  console.log('OK ' + out);
} catch (e) {
  console.log('ERR ' + String(e.message || e));
  process.exitCode = 1;
} finally {
  await browser.close();
}
