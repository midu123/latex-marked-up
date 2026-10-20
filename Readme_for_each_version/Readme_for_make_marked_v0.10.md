# make_marked_v0.10.py 使用说明

## 这是什么

一个 Python 脚本，用来给论文审稿回复自动生成 **marked-up（标红）版本**：
在新版 `.tex` 的基础上，把旧版→新版之间**新增 / 改动**的文字自动标红，其它所有格式、排版、行号、图注位置完全不变。

最终编译出的 PDF 除了字体颜色外，和新版 `.tex` 直接编译的 PDF **逐行一致**——审稿人可以拿着 response letter 对行号核对。同时，这也意味着，删除的内容不会再被显示/标记。

---

## 适用场景

- 论文修回（revision）时需要给审稿人看"我改了哪里"
- 期刊要求提交 marked-up manuscript，必须用红字标出修订内容
- 不想手动在 TeX 里逐处加 `\textcolor{red}{...}`，容易漏、容易破坏语法

---

## 快速开始

### 1. 命令格式

```bash
python make_marked_v0.10.py <旧版.tex> <新版.tex> <输出文件夹> [--name 文件名前缀] [--compile]
```

### 2. 实际运行示例

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.10.py" `
  "C:\Users\YourName\Documents\manuscript\old_version.tex" `
  "C:\Users\YourName\Documents\manuscript\new_version.tex" `
  "C:\Users\YourName\Documents\manuscript\marked-up_output" `
  --name "marked-up maintext"
```

### 3. 预期输出

```
[1/3] diff  old_version.tex  ->  new_version.tex
      wrote ...\marked-up maintext.tex  (62203 chars)
[2/3] copy dependencies (figure/, .cls/.bst/.bbl/.bib)
      .bbl copied: NO
[3/3] done. 打开 TeXstudio 编译 marked-up maintext.tex 即可。
```

> **`.bbl copied: NO` 是正常的**：新版 `.tex` 所在目录如果还没编译过，就没有预生成的 `.bbl` 文件。在 TeXstudio 里第一次编译时会自动跑 BibTeX 生成。

---

## 参数说明

| 参数 | 是否必填 | 说明 |
|---|---|---|
| `旧版.tex` | 必填 | 上一版本的 tex 文件路径（只读，不会被修改） |
| `新版.tex` | 必填 | 当前最新版本的 tex 文件路径（只读，输出 marked 版以它为底） |
| `输出文件夹` | 必填 | marked-up 结果存放目录，不存在会自动创建 |
| `--name 前缀` | 可选 | 输出 tex 的文件名前缀，默认 `marked-up maintext` |
| `--compile` | 可选 | 生成后自动用 pdflatex 编译两遍（默认关闭，推荐在 TeXstudio 里手动编译） |

---

## 输出文件夹里有什么

运行完成后，输出文件夹会包含：

| 文件 / 文件夹 | 来源 |
|---|---|
| `marked-up maintext.tex` | 脚本生成的标红主文件 |
| `figure/` | 从新版 tex 目录复制 |
| `*.cls`、`*.bst` | 从新版 tex 目录复制（文档类和参考文献样式） |
| `*.bib` | 从新版 tex 目录复制 |
| `*.bbl` | 如果新版目录有预编译的 .bbl 会复制；没有则编译时自动生成 |

**这些文件齐全后，直接用 TeXstudio 打开 `marked-up maintext.tex` 按 F5 编译即可。**

---

## 设计原理（为什么 PDF 能和新版完全一致）

脚本做了以下保护，确保标红不破坏排版：

1. **以新版为底**：删除旧版的内容不出现在输出里；新增/改动的片段只套一层 `\textcolor{red}{...}`，这是零宽度命令，不占额外排版空间。
2. **行级 diff → 行内 token 级 diff**：先按行比较，行内再逐词比较，只标真正改动的词，不整行重排。
3. **结构命令不标红**：`\label`、`\ref`、`\cite`、`\includegraphics`、`\caption` 等即使内容有变化也不包红，避免破坏 LaTeX 语法。
4. **数学块整块保护**：`\( ... \)`、`$...$`、`equation`、`align` 等环境整块不拆、不标红。
5. **表格环境整块保护**：`tabular`、`array`、`longtable` 等环境整块不标红，避免 `&` 和 `\\` 被包进 `\textcolor` 导致编译错误。
6. **`--` / `---` 原子处理**：连续两个或三个连字符作为一个整体，不会被拆成两个分别标红。
7. **相邻红块自动合并**：连续的红字合并成一个 `\textcolor{red}{...}`，避免出现 `red-black-red` 的颜色断裂。
8. **红块不跨段落**：遇到空行自动断开，不会出现"Paragraph ended before \@textcolor was complete"错误。

---

## 注意事项

- **不要修改旧版和新版 tex**：脚本对它们只读，所有改动都写在输出文件夹里。
- **路径含空格必须用双引号**：Windows 下路径有空格时一定要包引号，否则命令行会报错。
- **第一次编译跑两遍**：TeXstudio 里按 F5 编译后，再按一次 F5 让行号和参考文献稳定。
- **红字宽度导致行号可能偏移 1–2 行**：这是 `\textcolor` 的物理特性（红字和黑字字符宽度略有差别），审稿人可以接受，不影响内容核对。

---

## 常见问题

### Q: 编译时报 `! Extra }` 或 `Paragraph ended before \@textcolor`？
A: 通常是旧版 tex 里有特殊环境（如自定义表格、数学块）没被保护。检查报错行号附近是不是有表格或长公式，联系作者补充保护规则。

### Q: `.bbl copied: NO` 怎么办？
A: 正常现象。直接在 TeXstudio 里编译，它会自动跑 BibTeX 生成 `.bbl`。

### Q: 标红的范围不对，有些没改的字也红了 / 有些改了的字没红？
A: 脚本用 SequenceMatcher 做 diff，对大段连续修改可能合并粒度较粗。可以检查旧版和新版是否只是小改动，如果改动量大（整段重写），标红范围自然会大。

### Q: 输出的 PDF 和新版 PDF 行号对不上？
A: 红字宽度差异会导致换行点不同，行号可能偏移 1–3 行。这是正常的，内容完全一致，审稿人能定位到对应段落。
