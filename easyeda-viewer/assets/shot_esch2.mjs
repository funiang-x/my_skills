// shot_esch2.mjs — 用无头 Chrome 给 easyeda-viewer 里的文档截图（AI 的"眼睛"）
// 用法（cwd = viewer 仓库根，node_modules 里有 puppeteer-core）：
//   node .bridge-work/skill/shot_esch2.mjs <url> <out.png> [width] [height] [waitMs]
import puppeteer from 'puppeteer-core';
import { existsSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const CHROME = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync);
if (!CHROME) { console.log('ERR 找不到 Chrome/Edge'); process.exit(1); }

const [url, out] = process.argv.slice(2);
const width = Number(process.argv[4] || 1600);
const height = Number(process.argv[5] || 1000);
const waitMs = Number(process.argv[6] || 6000);

mkdirSync(dirname(resolve(out)), { recursive: true });
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, waitMs));
  // 尽量只留画布，去掉左侧树/右侧属性面板的干扰
  const canvasBox = await page.evaluate(() => {
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
