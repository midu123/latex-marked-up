# make_marked_v0.30.py 使用说明

## 这是什么

在 v0.20 的基础上，进一步把**删除的旧内容**用灰色字体+灰色删除线显示，**新增的内容**用红色字体显示。相当于 LaTeX 版的"修订模式"（track changes）。

## 三种颜色含义

| 颜色 | 含义 | LaTeX 实现 |
|---|---|---|
| 黑色（默认） | 新旧版本都有的内容（未改动） | 原样 |
| **红色** | 新版新增的内容 | `\textcolor{red}{...}` |
| **灰色 + 删除线** | 旧版有但新版删掉的内容 | `\textcolor{gray}{\sout{...}}` |

## 与 v0.20 的区别

| 项目 | v0.20 | v0.30 |
|---|---|---|
| 新增内容标红 | ✓ | ✓ |
| 删除内容显示 | ✗（完全不输出） | ✓（灰色+删除线） |
| 交叉引用展开为纯文本 | ✓ | ✓ |
| 输出 PDF 页数 | 和新版 maintext 基本一致 | **会比新版多几页**（因为被删的文字也显示出来了） |
| 适用场景 | 给审稿人看"改了哪里" | 给自己/导师看"完整的修订痕迹" |

## 用法

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.30.py" `
  "C:\Users\YourName\Documents\manuscript\old_version.tex" `
  "C:\Users\YourName\Documents\manuscript\new_version.tex" `
  "C:\Users\YourName\Documents\manuscript\marked-up_output" `
  --name "marked-up maintext"
```

### 示例

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.30.py" `
  "C:\Users\YourName\Documents\manuscript\old_version.tex" `
  "C:\Users\YourName\Documents\manuscript\new_version.tex" `
  "C:\Users\YourName\Documents\manuscript\marked-up_output" `
  --name "marked-up maintext"
```

## 编号替换规则（和 v0.20 一致）

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
- `--` 双连字符会作为整体处理，不会被拆开

## 处理流程

1. **先展开引用**：新旧两个版本的 tex 都先把 `\ref` / `\eqref` / `\cite` 展开成纯文本
2. **再做 diff**：基于展开后的文本做行级 + token 级 diff，找出新增、删除和改动的部分
3. **标记颜色**：新增的标红，删除的标灰+删除线，未改动的保持黑色
4. **复制依赖**：自动复制 figure 文件夹、.cls、.bst、.bbl 等依赖文件

## 自动注入的宏包

脚本会在输出 tex 的 `\begin{document}` 之前自动加一行：

```latex
\usepackage[normalem]{ulem}  % v0.30: 删除线支持
```

这个宏包提供 `\sout{...}`（删除线）命令。不需要手动加。

## 注意事项

1. **v0.30 的 PDF 页数会和新版 maintext 不一样**——因为被删的文字也显示出来了，占了额外的行。这是正常的，不是 bug。
2. 交叉引用展开逻辑和 v0.20 完全一样（`\ref{fig1}` → `Fig.1a`）。
3. 数学公式、表格、`\includegraphics` 等结构命令不会被标红或加删除线，保护 LaTeX 语法。
4. `--` / `---` 作为整体处理，不会被拆开。
5. 不修改任何源文件（旧版 tex、新版 tex、.aux、.bbl 都是只读）。
