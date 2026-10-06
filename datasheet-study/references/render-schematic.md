# 设计预览图离线渲染（circuitikz → PDF → PNG）

把**已确定的连接关系**（连接表 / 参数卡 / 讲解结论）渲染成一张原理图 PNG 给用户看。
全程离线：TeX 本地编译，不碰任何 EDA 工程。

## 铁律（先读这条）

**渲染是只读预览，一律离线出图。** 不启动 EDA、不建工程、不放件连线、不调
`easyeda-agent` / `easyeda-api` / 桥端口——那三条是 AI 落图链，只允许**用户当次点名**
时按 `WORKFLOW.md` ③ 后备路径走。用户说"画一张图 / 看看效果 / 渲染一下"= 要 PNG，
不是要你动他的立创EDA（实测踩过：把"渲染"理解成落图，被用户当场叫停）。

## 流程

1. **定布局**：从连接关系画草稿（纸上或脑内）。要点：电源箭头朝上、反馈回路绕运放
   上方走、网络端口（同名即同网）代替长飞线、电阻反馈网络竖放、预留引脚号标注位。
2. **写 .tex**：从下方模板起手，替换器件/网络/注释。中文标签用 `ctex`（`fontset=windows`）。
3. **编译转图**（单页 PDF 是中间产物，交付物是 PNG）：

   ```bash
   xelatex -interaction=nonstopmode <名>.tex
   pdftoppm -png -r 170 -singlefile <名>.pdf <名>
   ```

   判据：PDF 1 页、PNG 落盘。
4. **自检（不可跳）**：用读图工具**亲眼看** PNG，逐项查：
   - [ ] 标签无叠字（电容/电阻值与符号体、端口与地符号）
   - [ ] 无悬空符号（多余的地/电源孤岛）
   - [ ] 导线不穿器件体、不穿电源箭头、交叉处无圆点（交叉=不相连，有圆点=相连）
   - [ ] 引脚号与数据手册一致，网络名与连接表一致
   有一处修一轮再看；两轮仍有问题就把已确认的部分交付并说明残留项。
5. **交付**：PNG 链接给用户；`.tex` 源留盘（用户改值可重渲）；图底注释行带
   **手册页码**（与本 skill 的页码铁律一致）。

## 降级

| 缺什么 | 怎么办 |
|---|---|
| xelatex / circuitikz / pdftoppm（TeX 与 poppler） | 退回 ASCII 框图（会话里画）或结构化连接表；**不代装 TeX**，报缺即退 |
| 连接关系还没定 | 先出连接表让用户确认，再渲染——图是确认后的产物，不是替代确认 |

## 参数化模板（双运放：A 跟随器 + B 同相放大，单电源）

占位符：`<MPN>`、`<增益网络值>`、`<去耦值>`。单运放删 B 段；反相放大把输入网络改到 `.-`。

```latex
\documentclass[border=14pt]{standalone}
\usepackage[fontset=windows]{ctex}
\usepackage{circuitikz}
\usetikzlibrary{calc}
\begin{document}
\begin{circuitikz}[american, scale=1.05, transform shape, font=\small]
\tikzset{net/.style={draw=blue!60!black, fill=blue!8, rounded corners=2pt,
  font=\footnotesize\ttfamily, inner sep=3pt, text=blue!50!black}}

% ===== A 段（跟随器）=====
\node[op amp] (A) at (0,0) {};
\draw (A.+) -- ++(-0.9,0) node[net, anchor=east]{SIG\_IN};       % 输入端口
\draw (A.out) -- ++(0.5,0) coordinate (fbA) node[circ]{};         % 输出结点
\draw (fbA) -- ++(1.5,0) node[net, anchor=west]{BUF\_OUT};        % 输出端口
\draw (fbA) -- ++(0,1.15) -- ++(-2.6,0) -- ++(0,-0.9) -- (A.-);   % 反馈回路绕顶
\draw (A.up) -- ++(0,0.7) node[vcc]{+5V};                          % 脚8 V+
\node[anchor=south, font=\footnotesize] at ($(A.out)+(-0.25,0.14)$) {U1A};
\node[anchor=east, font=\tiny, text=gray] at ($(A.-)+(-0.08,0.16)$) {2};
\node[anchor=east, font=\tiny, text=gray] at ($(A.+)+(-0.08,-0.16)$) {3};
\node[anchor=south west, font=\tiny, text=gray] at ($(A.out)+(0.02,0.06)$) {1};

% ===== B 段（同相放大）=====
\node[op amp] (B) at (0,-3.4) {};
\draw (B.+) -- ++(-0.9,0) node[net, anchor=east]{BUF\_OUT};
\draw (B.-) -- ++(-0.5,0) coordinate (nB) node[circ]{};
\draw (nB) -- ++(0,-1.0) to[R=$R_g$, l_=$2.00\,k\Omega$] ++(0,-1.1) node[ground]{};
\draw (B.out) -- ++(0.6,0) coordinate (outB) node[circ]{};
\draw (outB) -- ++(1.5,0) node[net, anchor=west]{SIG\_OUT};
\draw (outB) -- ++(0,1.2) coordinate (rfBot);
\draw (rfBot) to[R=$R_f$, l_=$18.0\,k\Omega$] ++(0,1.1) coordinate (rfTop);
\draw (rfTop) -- ++(-3.5,0) coordinate (nBt);
\draw (nBt) -- (nBt |- nB) -- (nB);                                % Rf 顶线回 –IN
\draw (B.up) -- ++(0,0.7) node[vcc]{+5V};
\draw (B.down) -- ++(0,-0.5) node[ground]{};                       % 脚4 V- 接地
\node[anchor=east, font=\tiny, text=gray] at ($(B.-)+(-0.08,0.16)$) {6};
\node[anchor=east, font=\tiny, text=gray] at ($(B.+)+(-0.08,-0.16)$) {5};
\node[anchor=south west, font=\tiny, text=gray] at ($(B.out)+(0.02,0.06)$) {7};

% ===== 去耦 =====
\draw (6.2,1.7) node[vcc]{+5V} to[C] ++(0,-1.5) node[ground]{};
\node[anchor=west, font=\footnotesize] at ($(6.2,1.7)+(0.42,-0.75)$) {$C_1${=}100nF};

% ===== 标题与注释（注释带手册页码）=====
\node[anchor=south, font=\bfseries] at (3.2,2.9) {<MPN> 演示原理图};
\node[anchor=north, font=\footnotesize, text width=15cm, align=center] at (3.2,-6.4)
  {<增益说明与页码引用>};
\end{circuitikz}
\end{document}
```

> 模板已实测通过（2026-10-06，OPA2197 双通道 demo，xelatex + TeX Live 2026 +
> poppler pdftoppm）。换布局后**必须走流程第 4 步自检**——布局一改，叠字与穿越就要重查。
