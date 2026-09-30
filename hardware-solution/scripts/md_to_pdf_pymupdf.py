#!/usr/bin/env python3

"""
NextBoard 硬件方案 Markdown → PDF 转换脚本（PyMuPDF 版 / weasyprint 替代路径）

为什么存在这个脚本：
    同目录的 md_to_pdf.py 依赖 weasyprint，而 weasyprint 需要系统级 GTK/Pango 运行库。
    在缺少该库的机器上（例如 Windows + 无 MSYS2 GTK），`import weasyprint` 会直接报错：
        "WeasyPrint could not import some external libraries."
    本脚本改用 PyMuPDF（pip install pymupdf，纯 wheel、无系统依赖）完成同等工作，
    复用 md_to_pdf.py 中的 THEMES 配色方案，输出风格保持一致。

相比 weasyprint 的差异（已知）：
    1. CSS 的 @page 边距框（@top-center / @bottom-center / counter(pages)）不被 MuPDF 支持，
       改为渲染完成后用 PyMuPDF 逐页绘制页眉页脚与页码。
    2. 回退字体（Droid Sans Fallback 系）没有制表符（U+2500~U+257F）与 emoji 字形，
       直接用会渲染成实心黑块，因此渲染前做一次字形降级替换（见 GLYPH_FALLBACK）。
       源 md 文件不受影响，仅影响 PDF 呈现。

用法:
    python md_to_pdf_pymupdf.py input.md output.pdf [--title "方案标题"] [--theme green]
    python md_to_pdf_pymupdf.py --merge docs/hardware/ output.pdf [--theme green] \
        [--order "screen-board-selection.md,hardware-solution.md"]

依赖: pip install pymupdf markdown
"""

import sys
import os
import re
import argparse

import markdown
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from md_to_pdf import THEMES
except Exception:  # 极端情况下退化到内置配色
    THEMES = {"green": {"name": "工程翠绿", "primary": "#0F766E", "h2": "#1e8449",
                        "h3": "#2e86c1", "h4": "#5b2c6f", "body_color": "#2c3e50",
                        "subtitle_color": "#95a5a6", "bold_color": "#1a252f",
                        "blockquote_bg": "#f8f9fa", "blockquote_color": "#5d6d7e",
                        "code_bg": "#fdf2e9", "code_color": "#c0392b",
                        "pre_bg": "#f4f6f7", "pre_color": "#2c3e50", "pre_border": "",
                        "pre_radius": "3pt", "thead_bg": "#0F766E",
                        "td_border": "#bdc3c7", "even_row_bg": "#f8f9fa",
                        "hr_color": "#bdc3c7", "link_color": "#2e86c1",
                        "link_decoration": "none", "footer_counter": ""}}

CJK_FONT = "china-s"          # PyMuPDF 内置简体中文字体别名（仅用于页眉页脚/封面兜底）
PAGE_W, PAGE_H = pymupdf.paper_size("a4")
MARGIN_L, MARGIN_R = 46, 46
MARGIN_T, MARGIN_B = 62, 56

# ── 回退字体缺字形时的降级替换（只影响 PDF，不改源文件）──
GLYPH_FALLBACK = {}
for _s in "\u2500\u2501\u2504\u2505\u2508\u2509\u254c\u254d\u2550\u2508":
    GLYPH_FALLBACK[ord(_s)] = "-"
for _s in "\u2502\u2503\u2506\u2507\u250a\u250b\u254e\u254f\u2551":
    GLYPH_FALLBACK[ord(_s)] = "|"
for _s in "\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534\u253c\uff0b":
    GLYPH_FALLBACK[ord(_s)] = "+"
for _s in "\u2554\u2557\u255a\u255d\u2560\u2563\u2566\u2569\u256c":
    GLYPH_FALLBACK[ord(_s)] = "+"
for _s in "\u25b6\u25ba\u25b8\u27a4\u2192\u21d2":
    GLYPH_FALLBACK[ord(_s)] = ">"
for _s in "\u25c0\u25c4\u25c2\u2190":
    GLYPH_FALLBACK[ord(_s)] = "<"
for _s in "\u25b2\u25b4":
    GLYPH_FALLBACK[ord(_s)] = "^"
for _s in "\u25bc\u25be":
    GLYPH_FALLBACK[ord(_s)] = "v"
for _s in "\u2605\u2606\u25cf\u25cb":
    GLYPH_FALLBACK[ord(_s)] = "*"
for _s in "\u2022\u25aa\u25ab\u25b8\u2043":
    GLYPH_FALLBACK[ord(_s)] = "-"
for _s in "\u2705\u2714\u2713\u221a":
    GLYPH_FALLBACK[ord(_s)] = "[OK]"
for _s in "\u274c\u2717\u2718\u00d7":
    GLYPH_FALLBACK[ord(_s)] = "[X]"
for _s in "\u26a0\ufe0f\u2757\u2755":
    GLYPH_FALLBACK[ord(_s)] = "[!]"
GLYPH_FALLBACK[0xFE0F] = None    # 变体选择符，直接删掉
GLYPH_FALLBACK[0x200B] = None    # 零宽空格


def apply_glyph_fallback(text):
    """把回退字体没有字形的符号降级成 ASCII / 常见符号；返回 (新文本, 替换次数)"""
    n = sum(1 for ch in text if ord(ch) in GLYPH_FALLBACK)
    out = text.translate(GLYPH_FALLBACK)
    rest = len(re.findall(r'[\u2500-\u259f]', out))
    out = re.sub(r'[\u2500-\u257f]', '+', out)
    out = re.sub(r'[\u2580-\u259f]', '#', out)
    return out, n + rest


def build_css(theme_name):
    """生成 PyMuPDF Story 支持的 CSS 子集（不使用 @page 边距框，页眉页脚后绘制）"""
    t = THEMES.get(theme_name, THEMES["green"])
    return f"""
@page {{ size: A4; margin: {MARGIN_T}pt {MARGIN_R}pt {MARGIN_B}pt {MARGIN_L}pt; }}
body {{ font-family: sans-serif; font-size: 10.5pt; line-height: 1.72;
        color: {t['body_color']}; }}
h1 {{ font-size: 18pt; color: {t['primary']}; margin: 10pt 0 8pt 0;
      padding-bottom: 4pt; border-bottom: 1.6pt solid {t['primary']}; }}
h2 {{ font-size: 13.5pt; color: {t['h2']}; margin: 14pt 0 6pt 0; }}
h3 {{ font-size: 11.5pt; color: {t['h3']}; margin: 10pt 0 4pt 0; }}
h4 {{ font-size: 10.5pt; color: {t['h4']}; margin: 8pt 0 3pt 0; }}
p  {{ margin: 3pt 0; }}
blockquote {{ margin: 6pt 0; padding: 6pt 8pt 6pt 10pt;
              background: {t['blockquote_bg']}; border-left: 2.5pt solid {t['primary']};
              color: {t['blockquote_color']}; font-size: 10pt; }}
blockquote p {{ margin: 2pt 0; }}
strong, b {{ font-weight: bold; color: {t['bold_color']}; }}
code {{ font-family: monospace; background: {t['code_bg']}; color: {t['code_color']};
        font-size: 9pt; }}
pre {{ background: {t['pre_bg']}; color: {t['pre_color']}; padding: 6pt;
       font-size: 8pt; line-height: 1.35; white-space: pre-wrap;
       overflow-wrap: break-word; {t['pre_border']} }}
pre code {{ background: {t['pre_bg']}; color: inherit; font-size: 8pt; }}
table {{ width: 100%; border-collapse: collapse; margin: 6pt 0; font-size: 9pt; }}
thead th {{ background: {t['thead_bg']}; color: white; padding: 4pt 5pt;
            text-align: left; }}
tbody td {{ padding: 3.5pt 5pt; border-bottom: 0.5pt solid {t['td_border']}; }}
hr {{ border: none; border-top: 0.5pt solid {t['hr_color']}; margin: 8pt 0; }}
ul, ol {{ margin: 3pt 0; padding-left: 16pt; }}
li {{ margin-bottom: 1.5pt; }}
a {{ color: {t['link_color']}; text-decoration: {t['link_decoration']}; }}
"""


def md_to_body_html(md_text):
    """Markdown → HTML body，并剥离首个 H1 作为报告标题"""
    html_body = markdown.markdown(
        md_text, extensions=['tables', 'fenced_code', 'nl2br'], output_format='html5'
    )
    m = re.search(r'<h1>(.*?)</h1>', html_body)
    title = None
    if m:
        title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        html_body = html_body.replace(m.group(0), '', 1)
    return html_body, title


def collect_md(directory, order=None):
    """收集目录下的 .md 文件；--order 可指定优先顺序，其余按文件名追加"""
    files = [f for f in os.listdir(directory) if f.endswith('.md')]
    if not files:
        print(f"[ERROR] 目录 {directory} 下没有找到 .md 文件")
        sys.exit(1)
    if order:
        wanted = [x.strip() for x in order.split(',') if x.strip()]
        head = [f for f in wanted if f in files]
        tail = sorted([f for f in files if f not in head])
        files = head + tail
    else:
        files = sorted(files)

    merged = []
    for f in files:
        with open(os.path.join(directory, f), 'r', encoding='utf-8') as fh:
            merged.append(fh.read().strip())
        print(f"  合并: {f}")
    return "\n\n---\n\n".join(merged), files


def render_html_to_pdf(html, css, out_path, label=""):
    """用 PyMuPDF Story + DocumentWriter 分页渲染（纯 wheel，无系统依赖）"""
    story = pymupdf.Story(html=html, user_css=css)
    mediabox = pymupdf.Rect(0, 0, PAGE_W, PAGE_H)
    where = mediabox + (MARGIN_L, MARGIN_T, -MARGIN_R, -MARGIN_B)

    writer = pymupdf.DocumentWriter(out_path)
    more, pages, guard = 1, 0, 0
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
        pages += 1
        guard += 1
        if guard > 500:
            print(f"[WARN] {label}页数超过 500，强制终止（疑似分页死循环）")
            break
    writer.close()
    return pages


def build_cover_html(title, subtitle, meta_lines):
    """封面用 HTML + Story 渲染，保证与正文同一套字体（避免 insert_text 的字距问题）"""
    metas = "".join(f'<div class="cov-m">{m}</div>' for m in meta_lines)
    return (f'<div class="cov"><div class="cov-t">{title}</div>'
            f'<div class="cov-s">{subtitle}</div><hr class="cov-hr">{metas}</div>')


def cover_css(base_css, theme_name):
    t = THEMES.get(theme_name, THEMES["green"])
    return base_css + f"""
.cov {{ margin-top: 200pt; text-align: center; }}
.cov-t {{ font-size: 20pt; color: {t['primary']}; margin-bottom: 20pt; }}
.cov-s {{ font-size: 11pt; color: {t['subtitle_color']}; margin-bottom: 16pt; }}
.cov-hr {{ width: 220pt; margin-left: 141pt; margin-top: 6pt; margin-bottom: 18pt;
           border: 0; border-top: 1.3pt solid {t['primary']}; }}
.cov-m {{ font-size: 9.5pt; color: {t['subtitle_color']}; margin: 4pt 0; }}
"""


def add_headers_footers(doc, header_text, skip_first=True):
    """逐页绘制页眉 / 页脚（Story 不支持 CSS 边距框，改为后绘制）"""
    total = doc.page_count
    body_total = total - (1 if skip_first else 0)
    for i in range(doc.page_count):
        page = doc[i]
        if skip_first and i == 0:
            continue
        n = i if skip_first else i + 1
        page.insert_text(pymupdf.Point(MARGIN_L, MARGIN_T - 22), header_text,
                         fontname=CJK_FONT, fontsize=7.5, color=(0.58, 0.65, 0.65))
        page.draw_line(pymupdf.Point(MARGIN_L, MARGIN_T - 15),
                       pymupdf.Point(PAGE_W - MARGIN_R, MARGIN_T - 15),
                       color=(0.93, 0.95, 0.95), width=0.5)
        label = f"第 {n} 页 / 共 {body_total} 页"
        w = pymupdf.get_text_length(label, fontname=CJK_FONT, fontsize=7.5)
        page.insert_text(pymupdf.Point((PAGE_W - w) / 2, PAGE_H - MARGIN_B + 26), label,
                         fontname=CJK_FONT, fontsize=7.5, color=(0.58, 0.65, 0.65))
        page.draw_line(pymupdf.Point(MARGIN_L, PAGE_H - MARGIN_B + 18),
                       pymupdf.Point(PAGE_W - MARGIN_R, PAGE_H - MARGIN_B + 18),
                       color=(0.06, 0.46, 0.43), width=0.8)


def main():
    theme_names = ", ".join(f"{k} ({v['name']})" for k, v in THEMES.items())
    ap = argparse.ArgumentParser(description="NextBoard 硬件方案 Markdown → PDF（PyMuPDF 版）")
    ap.add_argument("input", help="输入 Markdown 文件或目录（配合 --merge）")
    ap.add_argument("output", help="输出 PDF 路径")
    ap.add_argument("--title", default=None, help="报告标题")
    ap.add_argument("--subtitle", default="NextBoard Hardware Solution", help="封面副标题")
    ap.add_argument("--theme", default="green", choices=list(THEMES.keys()),
                    help=f"配色方案: {theme_names}")
    ap.add_argument("--merge", action="store_true", help="合并目录下所有 .md 为一个 PDF")
    ap.add_argument("--order", default=None,
                    help="合并顺序（逗号分隔文件名），未列出的按文件名追加")
    ap.add_argument("--no-cover", action="store_true", help="不生成封面")
    ap.add_argument("--raw", action="store_true",
                    help="不做缺字形降级替换（制表符/emoji 会渲染为空白或黑块）")
    args = ap.parse_args()

    if args.merge:
        if not os.path.isdir(args.input):
            print(f"[ERROR] --merge 模式下 input 必须是目录: {args.input}")
            sys.exit(1)
        print(f"[INFO] 合并目录: {args.input}")
        md_text, files = collect_md(args.input, args.order)
    else:
        if not os.path.isfile(args.input):
            print(f"[ERROR] 文件不存在: {args.input}")
            sys.exit(1)
        with open(args.input, 'r', encoding='utf-8') as f:
            md_text = f.read()
        files = [os.path.basename(args.input)]

    if args.raw:
        md_fixed = md_text
    else:
        md_fixed, n_sub = apply_glyph_fallback(md_text)
        if n_sub:
            print(f"[INFO] 缺字形符号降级替换: {n_sub} 处（制表符/emoji → ASCII，源文件未改动）")

    html_body, auto_title = md_to_body_html(md_fixed)
    title, _ = apply_glyph_fallback(args.title or auto_title or "硬件方案报告")
    subtitle, _ = apply_glyph_fallback(args.subtitle)
    theme = THEMES.get(args.theme, THEMES["green"])
    print(f"[INFO] 配色方案: {theme['name']}")
    print(f"[INFO] 渲染器: PyMuPDF {pymupdf.__version__}")

    css = build_css(args.theme)
    tmp_body = args.output + ".body.tmp.pdf"
    body_pages = render_html_to_pdf(html_body, css, tmp_body, label="正文")

    doc = pymupdf.open()
    if not args.no_cover:
        tmp_cover = args.output + ".cover.tmp.pdf"
        meta_lines = [f"共 {len(files)} 份文档 · 正文 {body_pages} 页", "生成工具：PyMuPDF 渲染"]
        render_html_to_pdf(build_cover_html(title, subtitle, meta_lines),
                           cover_css(css, args.theme), tmp_cover, label="封面")
        with pymupdf.open(tmp_cover) as cd:
            doc.insert_pdf(cd)
        try:
            os.remove(tmp_cover)
        except OSError:
            pass
    with pymupdf.open(tmp_body) as bd:
        doc.insert_pdf(bd)
    try:
        os.remove(tmp_body)
    except OSError:
        pass

    add_headers_footers(doc, f"{title} | NextBoard Hardware Solution",
                        skip_first=not args.no_cover)

    try:
        doc.subset_fonts()
    except Exception as e:
        print(f"[WARN] 字体子集化失败（不影响使用）: {e}")

    doc.save(args.output, garbage=3, deflate=True)
    doc.close()

    size_kb = os.path.getsize(args.output) / 1024
    with pymupdf.open(args.output) as final:
        blank = [i + 1 for i in range(final.page_count)
                 if len(final[i].get_text().strip()) < 20]
        probe = final[min(1, final.page_count - 1)].get_text()[:56].replace("\n", " ")
        print(f"[OK] PDF 已生成: {args.output}")
        print(f"     总页数 {final.page_count}（含封面）· {size_kb:.0f} KB")
        print(f"     近空白页: {blank if blank else '无'}")
        print(f"     文本校验: {probe!r}")


if __name__ == "__main__":
    main()
