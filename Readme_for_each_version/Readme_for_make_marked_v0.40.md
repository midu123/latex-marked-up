# make_marked_v0.40.py 使用说明

## 这是什么

调用外部 `latexdiff` 命令生成标准修订标记，然后自动把所有交叉引用展开为纯文本编号。效果和 `latexdiff old.tex new.tex > diff.tex` 完全一致。

## 与其他版本的区别

| 项目 | v0.10 | v0.20 | v0.30 | v0.40 |
|---|---|---|---|---|
| 对比算法 | 自己实现 | 自己实现 | 自己实现 | **外部 latexdiff** |
| 删除内容显示 | 不显示 | 不显示 | 可能漏显示 | **完整显示所有删除内容** |
| 新增内容显示 | 红色 | 红色 | 红色 | 红色 |
| 删除内容显示 | 无 | 无 | 灰色删除线 | 灰色删除线 |
| 交叉引用展开 | 无 | ✓ | ✓ | ✓ |

## 用法

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.40.py" `
  "C:\Users\YourName\Documents\manuscript\old_version.tex" `
  "C:\Users\YourName\Documents\manuscript\new_version.tex" `
  "C:\Users\YourName\Documents\manuscript\marked-up_output" `
  --name "marked-up maintext"
```

### 示例

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.40.py" "C:\Users\YourName\Documents\manuscript\old_version.tex" "C:\Users\YourName\Documents\manuscript\new_version.tex" "C:\Users\YourName\Documents\manuscript\marked-up_output" --name "marked-up maintext"
```

## 处理流程

1. **展开交叉引用**：先把旧版和新版 tex 里的 `\ref` / `\eqref` / `\cite` 展开成纯文本（Fig.1a, Eq.(1), [6–11] 等）
2. **调用 latexdiff**：把展开后的旧版和新版 tex 写到临时文件，调用 `latexdiff` 生成 diff
3. **替换 preamble**：用新版的 preamble（保持字体格式不变），加上 latexdiff 的命令定义
4. **输出结果**：写到输出文件夹
5. **复制依赖**：自动复制 figure 文件夹、.cls、.bst、.bbl 等依赖文件

## 标记样式说明

latexdiff 生成的标记：
- `\DIFdel{...}` —— 旧版被删除的内容（灰色删除线）
- `\DIFadd{...}` —— 新版新增的内容（红色）
- `\DIFdelbegin ... \DIFdelend` —— 删除块的开始/结束
- `\DIFaddbegin ... \DIFaddend` —— 新增块的开始/结束

这些命令在 preamble 里自动定义，不需要手动加。

## 编号替换规则

和 v0.20 / v0.30 完全一样：

| 原命令 | 替换为 | 示例 |
|---|---|---|
| `\ref{fig1}` | `Fig.N` 或 `Fig.Nx` | `Fig.1a` |
| `\ref{tab1}` | `Table N` | `Table 1` |
| `\ref{eq1}` | `Eq.(N)` | `Eq.(1)` |
| `\cite{RN5,RN6,RN7}` | `[N–M]` | `[6–11]` |

## 注意事项

1. **系统需要安装 latexdiff**：TeX Live 已经自带了 latexdiff，不需要额外安装。
2. **建议先编译过一次新版 maintext.tex**，确保同目录下有最新的 `.aux` 文件。
3. 运行后，输出文件夹里的 tex 可以直接复制内容到别的地方用，不需要再改编号。
4. **v0.40 的 PDF 页数会比新版 maintext 多**——因为被删的文字也显示出来了，占了额外的行。这是正常的，不是 bug。
5. 不修改任何源文件（旧版 tex、新版 tex、.aux、.bbl 都是只读）。
