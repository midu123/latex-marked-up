# latex-marked-up

Automatically generate a marked-up LaTeX manuscript from two versions (old vs. new), highlighting changes for journal review responses.

## What It Does

Given an old `.tex` file and a new `.tex` file, this tool produces a new `.tex` file where:
- **Added / modified text** is highlighted in red (v0.10, v0.20, v0.30, v0.40)
- **Deleted text** is shown in gray with strikethrough (v0.30, v0.40)
- All formatting, layout, line numbers, and figure positions remain identical to the new version

This is especially useful when responding to peer review comments — reviewers can quickly see exactly what changed between submissions.

## Four Versions

| Version | New text | Deleted text | Cross-references | Diff engine | Best for |
|---|---|---|---|---|---|
| **v0.10** | Red highlight | Hidden (not output) | Kept as LaTeX commands | Built-in SequenceMatcher | Basic marked-up manuscript |
| **v0.20** | Red highlight | Hidden (not output) | **Auto-expanded to plain text** (Fig.1, [6–11], Eq.(1)) | Built-in SequenceMatcher | Copy-pasting text without manually converting `\ref` / `\cite` |
| **v0.30** | Red highlight | Gray + strikethrough | Auto-expanded | Built-in SequenceMatcher | Full revision tracking (shows both old and new) |
| **v0.40** | Red highlight | Gray + strikethrough | Auto-expanded | **External latexdiff** | Standard latexdiff-style diff with complete deletion visibility |

### v0.10 vs v0.20

v0.20 automatically expands all LaTeX cross-references into plain text:
- `\ref{fig1a}` → `Fig.1a`
- `\eqref{eq1}` → `Eq.(1)`
- `\cite{RN5,RN6,RN7}` → `[5–7]` (Nature-style range merging)

This means you can copy the generated `.tex` content directly without manually replacing `\ref` / `\cite` commands.

### v0.20 vs v0.30

v0.30 adds visible deletion tracking:
- Old text that was removed from the new version appears in **gray with strikethrough** (`\textcolor{gray}{\sout{...}}`)
- Newly added text appears in **red**
- Unchanged text stays black

Note: v0.30's PDF will have more pages than the new manuscript because deleted text is still visible.

### v0.30 vs v0.40

v0.40 uses the external `latexdiff` command instead of a built-in diff engine:
- **Complete deletion visibility**: All deleted text is shown (v0.30's built-in diff algorithm may match similar old/new sentences and hide some deletions)
- **Standard latexdiff format**: Uses `\DIFadd{...}` and `\DIFdel{...}` markup, same as running `latexdiff old.tex new.tex > diff.tex`
- **Same colors**: Red for additions, gray strikethrough for deletions
- **Same cross-reference expansion**: All `\ref` / `\cite` commands are expanded to plain text

Note: v0.40 requires a working `latexdiff` installation (TeX Live includes it by default).

## Quick Start

### v0.10 — Basic red highlight (no cross-reference expansion)

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.10.py" "C:\Users\YourName\Documents\manuscript\old_version.tex" "C:\Users\YourName\Documents\manuscript\new_version.tex" "C:\Users\YourName\Documents\manuscript\marked-up_output" --name "marked-up maintext"
```

### v0.20 — Red highlight + auto-expanded cross-references (Fig.1, [6–11], Eq.(1))

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.20.py" "C:\Users\YourName\Documents\manuscript\old_version.tex" "C:\Users\YourName\Documents\manuscript\new_version.tex" "C:\Users\YourName\Documents\manuscript\marked-up_output" --name "marked-up maintext"
```

### v0.30 — Full revision tracking (red for new, gray strikethrough for deleted)

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.30.py" "C:\Users\YourName\Documents\manuscript\old_version.tex" "C:\Users\YourName\Documents\manuscript\new_version.tex" "C:\Users\YourName\Documents\manuscript\marked-up_output" --name "marked-up maintext"
```

### v0.40 — Standard latexdiff-style diff with complete deletion visibility

```powershell
python "C:\Users\YourName\Documents\latex-marked-up\make_marked_v0.40.py" "C:\Users\YourName\Documents\manuscript\old_version.tex" "C:\Users\YourName\Documents\manuscript\new_version.tex" "C:\Users\YourName\Documents\manuscript\marked-up_output" --name "marked-up maintext"
```

Then open the generated `.tex` file in TeXstudio and compile normally.

## Command-Line Arguments

| Argument | Description |
|---|---|
| `old.tex` | Path to the old version `.tex` file (read-only) |
| `new.tex` | Path to the new version `.tex` file (read-only; output is based on this) |
| `out_dir` | Output directory for the marked-up files |
| `--name STEM` | Output filename prefix (default: `"marked-up maintext"`) |
| `--compile` | (Optional) Auto-compile with pdflatex after generation |

## How It Works

1. **Expand cross-references** (v0.20+): Both old and new tex files first have `\ref` / `\eqref` / `\cite` expanded to plain text. If `.aux` file is available, it reads actual numbering; otherwise it scans the tex source to figure out figure/table/equation numbering in order.

2. **Diff**:
   - **v0.10 / v0.20 / v0.30**: Line-level diff first, then token-level diff within changed lines. Math blocks, `\includegraphics`, `\label`, and other structural commands are protected (not highlighted) to avoid breaking LaTeX syntax.
   - **v0.40**: Calls the external `latexdiff` command to generate standard `\DIFadd{...}` / `\DIFdel{...}` markup.

3. **Post-processing**:
   - **v0.10 / v0.20 / v0.30**: Consecutive highlighted fragments (including spaces between them) are merged into a single `\textcolor{red}{...}` block to avoid broken `--` rendering.
   - **v0.40**: Replaces latexdiff's auto-generated preamble with the new manuscript's original preamble (preserving font and layout), then appends latexdiff command definitions.

4. **Copy dependencies**: Automatically copies `figure/` folder, `.cls`, `.bst`, and `.bbl` files to the output directory so the marked-up tex compiles standalone.

## Output

The output directory contains:
- `marked-up maintext.tex` — the marked-up LaTeX source
- `figure/` — copied figure folder
- `.bbl` — bibliography file (if available)
- Any other required `.cls` / `.bst` files

You can open the `.tex` file directly in TeXstudio and compile — no additional setup needed.

## Notes

- The tool **never modifies** any input files (old tex, new tex, .aux, .bbl) — it only reads them.
- `--` and `---` are treated as atomic tokens and will not be split across highlighted blocks.
- Minor layout differences (e.g., line break position on one page) may occur due to `\textcolor` command boundaries affecting LaTeX's line-breaking algorithm. This is a natural side effect of text coloring and does not affect content or figures.
- v0.20 automatically injects the bibliography from `.bbl` file, so the output tex no longer needs a separate `.bib` file to compile.
- v0.30 / v0.40 PDF will have more pages than the new manuscript because deleted text is still visible.

## Requirements

- Python 3.6+
- A working LaTeX distribution (e.g., TeX Live) for compiling the output
- **v0.40 only**: `latexdiff` command available in PATH (included with TeX Live 2026+)

## License

MIT License — feel free to use, modify, and distribute.
