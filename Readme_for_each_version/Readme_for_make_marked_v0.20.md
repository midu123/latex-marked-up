# make_marked_v0.20.py 使用说明

## 这是什么

在 v0.10 的基础上，进一步把所有**交叉引用自动展开为纯文本编号**。生成的 tex 文件复制出来时，不再有 `\ref{fig1}`、`\eqref{eq1}`、`\cite{RN5}` 这类命令，而是直接写死 "Fig.2a"、"(1)"、"[6–11]" 等文本。

## 与 v0.10 的区别

| 项目 | v0.10 | v0.20 |
|---|---|---|
| 新增/改动文字标红 | ✓ | ✓ |
| `\ref{fig1}` | 保留原命令（需要 .aux 文件） | 自动替换成 `Fig.2a` |
| `\eqref{eq1}` | 保留原命令 | 自动替换成 `Eq.(1)` |
| `\cite{RN5,RN6,RN7}` | 保留原命令（需要 .bbl/.bib） | 自动替换成 `[5–7]` |
| `\bibliography{...}` | 保留原命令 | 自动替换成 .bbl 里的完整参考文献列表 |
| 输出 tex 能否独立编译 | 需要 .aux / .bbl / .bib | **不需要**（自带编号和参考文献） |

## 用法

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.20.py" `
  "C:\Users\YourName\Documents\manuscript\old_version.tex" `
  "C:\Users\YourName\Documents\manuscript\new_version.tex" `
  "C:\Users\YourName\Documents\manuscript\marked-up_output" `
  --name "marked-up maintext"
```

### 示例

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.20.py" "C:\Users\YourName\Documents\manuscript\old_version.tex" "C:\Users\YourName\Documents\manuscript\new_version.tex" "C:\Users\YourName\Documents\manuscript\marked-up_output" --name "marked-up maintext"
```

## 编号替换规则

脚本自动从新版 tex 同目录下的 `.aux` 文件读取编号；如果 `.aux` 不存在，会自动从 tex 源码扫描 figure/table/equation 环境按出现顺序编号。

| 原命令 | label 名前缀 | 替换为 | 示例 |
|---|---|---|---|
| `\ref{fig1}` | fig- | `Fig.N` 或 `Fig.Nx` | `Fig.1a` |
| `\ref{tab1}` | tab- | `Table N` | `Table 1` |
| `\ref{eq1}` | eq- | `Eq.(N)` | `Eq.(1)` |
| `\eqref{eq1}` | eq- | `Eq.(N)` | `Eq.(1)` |
| `\ref{sec1}` | sec- | `Section N` | `Section 3` |
| `\cite{RN5}` | — | `[N]` | `[6]` |
| `\cite{RN5,RN6}` | — | `[N, M]`（2个连续） | `[1, 2]` |
| `\cite{RN5,RN6,RN7}` | — | `[N–M]`（3个以上连续） | `[6–11]` |

### 智能前缀检测

- 如果原文已经写了 "Fig. \ref{fig1a}"，脚本不会再加 "Fig." 前缀，直接展开成 `Fig.1a`
- 如果原文写了 "(\ref{eq1})"，脚本展开成 `(Eq.(1))` 还是 `(1)`，取决于上下文
- `--` 双连字符会作为整体标红，不会拆开

## 处理流程

1. **先展开引用**：新旧两个版本的 tex 都先把 `\ref` / `\eqref` / `\cite` 展开成纯文本
2. **再做 diff**：基于展开后的文本做行级 + token 级 diff，找出新增和改动的部分
3. **合并红块**：把连续的红块合并，避免频繁开关 `\textcolor{red}{...}`
4. **复制依赖**：自动复制 figure 文件夹、.cls、.bst、.bbl 等依赖文件

## 注意事项

1. **建议先编译过一次新版 maintext.tex**，确保同目录下有最新的 `.aux` 文件。如果 `.aux` 不存在，脚本会自动从 tex 源码扫描编号（可能和实际 PDF 略有差异）。
2. 运行后，输出文件夹里的 tex 可以直接复制内容到别的地方用，不需要再改编号。
3. **排版一致性说明**：输出 PDF 和新版 maintext PDF 内容基本一致（只是新增/改动的文字是红色）。由于 `\textcolor{red}{...}` 命令的边界会微妙影响 LaTeX 断行算法，少数页面可能有一行的换行位置略有不同，导致后续行号偏移 1 行。这是 LaTeX 排版的固有特性，不影响内容和图表的一致性。
4. 不修改任何源文件（旧版 tex、新版 tex、.aux、.bbl 都是只读）。
