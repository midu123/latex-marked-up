# -*- coding: utf-8 -*-
"""
make_marked_v0.20.py — 在 v0.10 基础上，进一步把所有交叉引用（\\ref / \\eqref / \\cite）
和参考文献列表自动展开为纯文本编号。生成的 tex 复制出来时不再依赖 .aux / .bbl。

用法:
    python make_marked_v0.20.py <old.tex> <new.tex> <out_dir> [--name STEM] [--compile]

v0.20 新增:
  1. 自动读取新版 tex 同目录下的 <stem>.aux，建立 label -> number 映射：
       \\ref{fig1}  ->  Fig. 1
       \\ref{tab1}  ->  Table 1
       \\eqref{eq1} ->  (1)
       \\ref{sec1}  ->  Section 1
  2. 自动读取 <stem>.aux 里的 \\bibcite，建立 cite key -> number 映射：
       \\cite{RN5} -> [5]
       \\cite{RN5, RN6} -> [5, 6]
  3. 把 \\bibliography{Reference} 直接替换成 .bbl 文件里的 thebibliography 环境，
     这样输出 tex 不再需要 .bib / .bst / BibTeX 即可独立编译。

其它行为与 v0.10 完全一致。
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# 结构 / 元信息命令（同 v0.10）
# ---------------------------------------------------------------------------
EXCLUDED_CMD = {
    '\\label', '\\ref', '\\pageref', '\\eqref',
    '\\cite', '\\citep', '\\citet', '\\nocite',
    '\\bibliographystyle', '\\bibliography', '\\input', '\\include',
    '\\usepackage', '\\documentclass',
    '\\newcommand', '\\renewcommand', '\\newtheorem', '\\providecommand',
    '\\DeclareMathOperator', '\\DeclareRobustCommand',
    '\\maketitle', '\\linenumbers', '\\raggedbottom', '\\appendix',
    '\\setcounter', '\\addtocounter', '\\setlength', '\\addtolength',
    '\\title', '\\author', '\\affil', '\\email',
    '\\fnm', '\\sur', '\\orgdiv', '\\orgname', '\\orgaddress',
    '\\street', '\\city', '\\postcode', '\\state', '\\country',
    '\\keywords', '\\abstract', '\\thanks', '\\footnote',
    '\\includegraphics', '\\pagenumbering', '\\tableofcontents',
    '\\thispagestyle', '\\pagestyle',
    '\\caption', '\\caption*',
    '\\textbf', '\\textit', '\\emph', '\\textrm', '\\textsf', '\\textsc',
    '\\textsl', '\\texttt', '\\textsuperscript', '\\textsubscript',
}
CONTENT_CMDS = {
    '\\caption', '\\caption*',
    '\\textbf', '\\textit', '\\emph', '\\textrm', '\\textsf', '\\textsc',
    '\\textsl', '\\texttt', '\\textsuperscript', '\\textsubscript',
}
SINGLE_CMD = {'\\\\', '\\%', '\\&', '\\#', '\\$', '\\_', '\\{', '\\}',
              '\\,', '\\;', '\\!', '\\ ', '\\~', '\\^', '\\-', '\\=', '\\>',
              '\\[', '\\]', '\\|', '\\/', '\\@', '\\\n'}

MATH_ENVS = {'equation', 'align', 'gather', 'multiline', 'eqnarray',
             'bmatrix', 'matrix', 'pmatrix', 'vmatrix', 'Vmatrix',
             'cases', 'split', 'aligned', 'gathered', 'array',
             'subequations', 'equation*', 'align*', 'gather*',
             'multiline*', 'eqnarray*', 'bmatrix*', 'array*',
             'tabular', 'tabular*', 'tabularx', 'tabulary', 'longtable',
             'threeparttable', 'threeparttablex', 'csvtable'}


def _cmd_name(text):
    m = re.match(r'(\\[A-Za-z]+\*?)', text)
    return m.group(1) if m else text


def tokenize_line(line):
    toks = []
    n = len(line)
    i = 0
    while i < n:
        c = line[i]
        if c == '\\':
            j = i + 1
            if j < n and line[j] in '([':
                opener = line[j]
                closer = ')' if opener == '(' else ']'
                k = j + 1
                depth = 0
                end = -1
                while k < n:
                    if line[k] == '\\' and k + 1 < n:
                        nxt = line[k + 1]
                        if nxt == opener:
                            depth += 1
                        elif nxt == closer:
                            if depth == 0:
                                end = k + 2
                                break
                            depth -= 1
                        k += 2
                    else:
                        k += 1
                if end != -1:
                    toks.append(('MATH', line[i:end]))
                    i = end
                    continue
            if j < n and line[j].isalpha():
                while j < n and line[j].isalpha():
                    j += 1
                if j < n and line[j] == '*':
                    j += 1
                cmd = line[i:j]
                if cmd in CONTENT_CMDS:
                    toks.append(('CMD', cmd))
                    i = j
                    continue
                while j < n and (line[j] == '[' or line[j] == '{'):
                    if line[j] == '[':
                        k = j + 1
                        depth = 1
                        closed = False
                        while k < n and depth > 0:
                            if line[k] == '[':
                                depth += 1
                            elif line[k] == ']':
                                depth -= 1
                                if depth == 0:
                                    closed = True
                                    k += 1
                                    break
                            k += 1
                        if closed:
                            cmd += line[j:k]
                            j = k
                        else:
                            break
                    else:
                        k = j + 1
                        depth = 1
                        closed = False
                        while k < n and depth > 0:
                            if line[k] == '{':
                                depth += 1
                            elif line[k] == '}':
                                depth -= 1
                                if depth == 0:
                                    closed = True
                                    k += 1
                                    break
                            k += 1
                        if closed:
                            cmd += line[j:k]
                            j = k
                        else:
                            break
                toks.append(('CMD', cmd))
                i = j
            else:
                j = i + 2 if i + 1 < n else i + 1
                toks.append(('CMD', line[i:j]))
                i = j
        elif c == '$':
            if i + 1 < n and line[i + 1] == '$':
                j = line.find('$$', i + 2)
                if j == -1:
                    toks.append(('MATH', line[i:]))
                    break
                toks.append(('MATH', line[i:j + 2]))
                i = j + 2
            else:
                j = line.find('$', i + 1)
                if j == -1:
                    toks.append(('MATH', line[i:]))
                    break
                toks.append(('MATH', line[i:j + 1]))
                i = j + 1
        elif c in '{}':
            toks.append(('BRACE', c))
            i += 1
        elif c in ' \t':
            j = i
            while j < n and line[j] in ' \t':
                j += 1
            toks.append(('SPACE', line[i:j]))
            i = j
        elif c == '%':
            toks.append(('COMMENT', line[i:]))
            break
        elif c in '&#~^_':
            toks.append(('SPEC', c))
            i += 1
        elif c == '-':
            j = i
            while j < n and line[j] == '-' and (j - i) < 3:
                j += 1
            toks.append(('TXT', line[i:j]))
            i = j
        elif c.isalnum():
            j = i
            while j < n and line[j].isalnum():
                j += 1
            toks.append(('TXT', line[i:j]))
            i = j
        else:
            toks.append(('TXT', c))
            i += 1
    return toks


def _wrap_tok(tok):
    kind, text = tok
    if kind in ('SPACE', 'BRACE', 'SPEC', 'COMMENT'):
        return text, False
    if kind == 'BLK':
        return text, False
    if kind == 'CMD':
        if text.startswith('\\begin{') or text.startswith('\\end{'):
            return text, False
        if text in SINGLE_CMD:
            return text, False
        if _cmd_name(text) in EXCLUDED_CMD:
            return text, False
        return text, True
    if kind in ('MATH', 'MATHX'):
        return text, False
    if text == '' or text == '\n':
        return text, False
    return text, True


def try_expand_math(text):
    if text.startswith('$$') and text.endswith('$$') and len(text) >= 4:
        body = text[2:-2]
    elif text.startswith('$') and text.endswith('$') and len(text) >= 2:
        body = text[1:-1]
    else:
        return None
    body = body.strip()
    if not body:
        return None
    out = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c.isalnum():
            j = i
            while j < n and body[j].isalnum():
                j += 1
            out.append(body[i:j])
            i = j
        elif c in ' \t':
            i += 1
        elif c in '.,-+()[]=<>·×/':
            out.append(c)
            i += 1
        elif c == '\\':
            m = re.match(r'\\(times|cdot)\b', body[i:])
            if m:
                out.append('×' if m.group(1) == 'times' else '·')
                i += m.end()
                continue
            m = re.match(r'\\(mathrm|text|mathbf|mathit|mathsf|mathtt)\*?\{([^{}]*)\}', body[i:])
            if m:
                arg = m.group(2)
                if re.search(r'[\\{}^_&$]', arg):
                    return None
                out.append(arg.strip())
                i += m.end()
                continue
            return None
        elif c in '^_&%{}':
            return None
        else:
            return None
    return out if out else None


def prep_seq(toks):
    compare, out = [], []
    for kind, text in toks:
        if kind == 'MATH':
            sub = try_expand_math(text)
            if sub is not None:
                for k, s in enumerate(sub):
                    compare.append(s)
                    out.append(('MATHX', text if k == 0 else ''))
                continue
        compare.append(text)
        out.append((kind, text))
    return compare, out


def merge_math_blocks(lines):
    out, flags = [], []
    n = len(lines)
    i = 0
    while i < n:
        m = re.search(r'\\begin\{([a-zA-Z*]+)\}', lines[i])
        env = m.group(1) if m else ''
        if env in MATH_ENVS:
            endpat = re.compile(r'\\end\{' + re.escape(env) + r'\}')
            j = i
            while j < n and not endpat.search(lines[j]):
                j += 1
            out.append('\n'.join(lines[i:j + 1]))
            flags.append(True)
            i = j + 1
        else:
            out.append(lines[i])
            flags.append(False)
            i += 1
    return out, flags


# ---------------------------------------------------------------------------
# v0.20: 读取 .aux，建立 label/cite 映射
# ---------------------------------------------------------------------------
def read_aux(aux_path):
    """从 .aux 文件读取 \newlabel{lbl}{{num}{...}} 和 \bibcite{key}{num}。
    返回 (label_map, cite_map)。
    """
    label_map = {}
    cite_map = {}
    if not os.path.isfile(aux_path):
        return label_map, cite_map
    txt = io.open(aux_path, encoding='utf-8', errors='replace').read()
    # \newlabel{fig1}{{1}{2}{...}{fig.1}{}}
    for m in re.finditer(r'\\newlabel\{([^}]+)\}\{\{([^}]*)\}', txt):
        label = m.group(1)
        num = m.group(2).strip()
        label_map[label] = num
    # \bibcite{RN5}{1} 或 \bibcite{RN5}{{1}{}{{}}{{}}}
    for m in re.finditer(r'\\bibcite\{([^}]+)\}\{\{?(\d+)', txt):
        cite_map[m.group(1)] = m.group(2).strip()
    return label_map, cite_map


def _ref_text(label, label_map):
    """根据 label 名前缀决定输出格式。"""
    num = label_map.get(label)
    if num is None:
        return None
    low = label.lower()
    if low.startswith('fig'):
        return 'Fig. ' + num
    if low.startswith('tab'):
        return 'Table ' + num
    if low.startswith('eq'):
        return '(' + num + ')'
    if low.startswith('sec'):
        return 'Section ' + num
    if low.startswith('supp'):
        return 'Supplementary ' + num
    return num


def scan_labels_from_tex(tex_text):
    """从 tex 本身扫描 figure/table/equation 环境，按出现顺序编号。
    用于 .aux 不存在时的 fallback。
    """
    label_map = {}
    fig_num = 0
    tab_num = 0
    eq_num = 0

    cur_fig = False
    cur_tab = False
    cur_eq = False

    for line in tex_text.splitlines():
        if re.search(r'\\begin\{figure\*?\}', line):
            cur_fig = True
        elif re.search(r'\\begin\{table\*?\}', line):
            cur_tab = True
        elif re.search(r'\\begin\{equation\*?\}', line):
            cur_eq = True
        elif re.search(r'\\end\{figure\*?\}', line):
            cur_fig = False
        elif re.search(r'\\end\{table\*?\}', line):
            cur_tab = False
        elif re.search(r'\\end\{equation\*?\}', line):
            cur_eq = False

        for m in re.finditer(r'\\label\{([^}]+)\}', line):
            lbl = m.group(1)
            low = lbl.lower()
            if low.startswith('fig') and cur_fig:
                fig_num += 1
                label_map[lbl] = str(fig_num)
            elif low.startswith('tab') and cur_tab:
                tab_num += 1
                label_map[lbl] = str(tab_num)
            elif low.startswith('eq') and cur_eq:
                eq_num += 1
                label_map[lbl] = str(eq_num)
    return label_map


def expand_refs(text, label_map, cite_map):
    """把 \\ref{...}, \\eqref{...}, \\cite{...} 全部替换成纯文本。
    智能判断前面是否已有 Fig./Table/Eq. 前缀，避免重复。
    """
    if not label_map and not cite_map:
        return text

    def _has_prefix_before(text, pos, prefixes):
        ctx = text[max(0, pos - 20):pos]
        for p in prefixes:
            if ctx.rstrip().endswith(p):
                return True
        return False

    def repl_ref(m):
        inner = m.group(1)
        labels = [x.strip() for x in inner.split(',')]
        pos = m.start()
        parts = []
        for lbl in labels:
            num = label_map.get(lbl)
            if num is None:
                return m.group(0)
            low = lbl.lower()
            if low.startswith('fig'):
                # 识别 Fig. / Figs. 前缀
                if _has_prefix_before(text, pos, ['Figs.', 'Figs ', 'Fig.', 'Fig ']):
                    parts.append(num)
                else:
                    parts.append('Fig.' + num)  # 无空格，和原版 PDF 一致
            elif low.startswith('tab'):
                if _has_prefix_before(text, pos, ['Table', 'Tab.']):
                    parts.append(num)
                else:
                    parts.append('Table ' + num)
            elif low.startswith('eq'):
                if _has_prefix_before(text, pos, ['Eq.', 'Eq ']):
                    parts.append(num)
                else:
                    parts.append('Eq.(' + num + ')')  # 无空格
            elif low.startswith('sec'):
                if _has_prefix_before(text, pos, ['Section', 'Sec.']):
                    parts.append(num)
                else:
                    parts.append('Section ' + num)
            else:
                parts.append(num)
        return ', '.join(parts)

    def repl_eqref(m):
        num = label_map.get(m.group(1))
        if num is None:
            return m.group(0)
        return '(' + num + ')'

    def repl_cite(m):
        inner = m.group(1)
        keys = [x.strip() for x in inner.split(',')]
        nums = []
        for k in keys:
            n = cite_map.get(k)
            if n is None:
                return m.group(0)
            nums.append(int(n))
        nums_sorted = sorted(nums)
        # Nature 格式：2 个连续用逗号，3 个以上连续用范围
        ranges = []
        start = prev = nums_sorted[0]
        for n in nums_sorted[1:]:
            if n == prev + 1:
                prev = n
            else:
                if start == prev:
                    ranges.append(str(start))
                elif prev == start + 1:
                    ranges.append(str(start) + ', ' + str(prev))
                else:
                    ranges.append(str(start) + '–' + str(prev))
                start = prev = n
        if start == prev:
            ranges.append(str(start))
        elif prev == start + 1:
            ranges.append(str(start) + ', ' + str(prev))
        else:
            ranges.append(str(start) + '–' + str(prev))
        return '[' + ', '.join(ranges) + ']'

    text = re.sub(r'\\eqref\{([^}]+)\}', repl_eqref, text)
    text = re.sub(r'\\ref\*?\{([^}]+)\}', repl_ref, text)
    text = re.sub(r'\\cite[a-z]*\*?(?:\[[^\]]*\])*\{([^}]+)\}', repl_cite, text)
    return text


def expand_bibliography(text, bbl_path):
    """把 \\bibliography{...} 替换成 .bbl 文件内容（thebibliography 环境）。"""
    if not os.path.isfile(bbl_path):
        return text
    bbl = io.open(bbl_path, encoding='utf-8', errors='replace').read().strip()
    # 用 lambda 避免 bbl 内容里的反斜杠被当成 re.sub 的转义
    return re.sub(r'\\bibliography\{[^}]*\}', lambda m: bbl, text)


# ---------------------------------------------------------------------------
# 合并红块（同 v0.10）
# ---------------------------------------------------------------------------
def merge_red_segments(chunks):
    merged = []
    buf = []
    buf_open = False

    def brace_balanced(s):
        depth = 0
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == '\\' and i + 1 < n:
                i += 2
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth < 0:
                    return False
            i += 1
        return depth == 0

    def _emit_red_block(content):
        """把一段连续的红内容写成 \textcolor{red}{...}，尽量不拆行，避免断行位置偏移。"""
        content = content
        # 如果跨段落（含连续两个换行 = 空行），必须按段落拆开，因为 \textcolor 不能跨 paragraph
        para_parts = re.split(r'(\n\s*\n)', content)
        out = []
        for pp in para_parts:
            if not pp:
                continue
            # 空行分隔符原样输出
            if re.fullmatch(r'\n\s*\n', pp):
                out.append(pp)
                continue
            # 段落内部：如果花括号平衡，整段包红（内部换行 = 空格，不影响断行）
            stripped = pp.strip(' \t')
            if stripped and brace_balanced(pp):
                out.append('\\textcolor{red}{' + pp + '}')
            else:
                # 花括号不平衡时退回按行处理（兜底）
                for line_idx, line in enumerate(pp.split('\n')):
                    if line.strip(' \t') and brace_balanced(line):
                        out.append('\\textcolor{red}{' + line + '}')
                    else:
                        out.append(line)
                    if line_idx < len(pp.split('\n')) - 1:
                        out.append('\n')
        return ''.join(out)

    def flush():
        nonlocal buf, buf_open
        if buf:
            content = ''.join(buf)
            if content.strip(' \t') and brace_balanced(content):
                merged.append(_emit_red_block(content))
            else:
                merged.append(content)
            buf = []
            buf_open = False

    for text, is_red in chunks:
        if is_red:
            if '\n' in text:
                # 先 flush 当前 buf，再直接按段落处理这段含换行的红内容
                flush()
                merged.append(_emit_red_block(text))
            else:
                buf.append(text)
                buf_open = True
        else:
            if buf_open and text:
                stripped = text.strip(' \t')
                if stripped == '':
                    # 只有空格和换行
                    newline_count = text.count('\n')
                    if newline_count <= 1:
                        # 单个换行或纯空格，合并到红块（避免红块被逐行拆碎导致断行偏移）
                        buf.append(text)
                    else:
                        # 空行（段落分隔），flush 后保留空行
                        flush()
                        merged.append(text)
                else:
                    # 有实际黑色文字，flush
                    flush()
                    merged.append(text)
            else:
                merged.append(text)
    flush()
    return ''.join(merged)


def diff_to_marked(old_text, new_text):
    old_blocks, old_flags = merge_math_blocks(old_text.splitlines())
    new_blocks, new_flags = merge_math_blocks(new_text.splitlines())
    chunks = []

    sm = SequenceMatcher(None, old_blocks, new_blocks, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for blk in new_blocks[j1:j2]:
                chunks.append((blk + '\n', False))
        elif tag == 'delete':
            pass
        elif tag == 'insert':
            for blk, fl in zip(new_blocks[j1:j2], new_flags[j1:j2]):
                if fl:
                    chunks.append((blk + '\n', False))
                else:
                    toks = tokenize_line(blk) + [('TXT', '\n')]
                    for t in toks:
                        w, r = _wrap_tok(t)
                        chunks.append((w, r))
        elif tag == 'replace':
            old_toks = []
            for blk, fl in zip(old_blocks[i1:i2], old_flags[i1:i2]):
                if fl:
                    old_toks.append(('BLK', blk))
                else:
                    old_toks.extend(tokenize_line(blk))
                old_toks.append(('TXT', '\n'))
            new_toks = []
            for blk, fl in zip(new_blocks[j1:j2], new_flags[j1:j2]):
                if fl:
                    new_toks.append(('BLK', blk))
                else:
                    new_toks.extend(tokenize_line(blk))
                new_toks.append(('TXT', '\n'))
            old_cmp, old_out = prep_seq(old_toks)
            new_cmp, new_out = prep_seq(new_toks)
            sm2 = SequenceMatcher(None, old_cmp, new_cmp, autojunk=False)
            for tag2, a1, a2, b1, b2 in sm2.get_opcodes():
                if tag2 == 'equal':
                    for t in new_out[b1:b2]:
                        chunks.append((t[1], False))
                elif tag2 == 'delete':
                    pass
                else:
                    for t in new_out[b1:b2]:
                        w, r = _wrap_tok(t)
                        chunks.append((w, r))

    result = merge_red_segments(chunks)
    idx = result.find('\\end{document}')
    if idx != -1:
        eol = result.find('\n', idx)
        if eol != -1:
            result = result[:eol + 1]
    return result


def copy_dependencies(new_tex_path, out_dir, stem):
    src = os.path.dirname(os.path.abspath(new_tex_path))
    fig_src = os.path.join(src, 'figure')
    if os.path.isdir(fig_src):
        shutil.copytree(fig_src, os.path.join(out_dir, 'figure'),
                        dirs_exist_ok=True)
    for f in os.listdir(src):
        if f.endswith('.cls') or f.endswith('.bst'):
            shutil.copy2(os.path.join(src, f), out_dir)
    new_tex = io.open(new_tex_path, encoding='utf-8', errors='replace').read()
    bib_m = re.findall(r'\\bibliography\{([^}]*)\}', new_tex)
    bib_name = bib_m[0] if bib_m else 'Reference'
    copied_bbl = False
    for cand in (os.path.join(src, bib_name + '.bbl'),
                 os.path.join(src, stem + '.bbl'),
                 os.path.join(src, 'maintext.bbl')):
        if os.path.isfile(cand):
            shutil.copy2(cand, os.path.join(out_dir, bib_name + '.bbl'))
            shutil.copy2(cand, os.path.join(out_dir, stem + '.bbl'))
            copied_bbl = True
            break
    for cand in (os.path.join(src, bib_name + '.bib'),
                 os.path.join(src, 'Reference.bib')):
        if os.path.isfile(cand):
            shutil.copy2(cand, os.path.join(out_dir, bib_name + '.bib'))
            break
    for m in re.findall(r'\\input\{([^}]+)\}', new_tex):
        if not m.endswith('.tex'):
            m += '.tex'
        p = os.path.join(src, m)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(out_dir, m))
    return copied_bbl


def compile_pdf(out_dir, stem):
    tex = os.path.join(out_dir, stem + '.tex')
    log_path = os.path.join(out_dir, stem + '.log')
    args = ['pdflatex', '-interaction=nonstopmode', os.path.basename(tex)]
    for _ in range(2):
        subprocess.run(args, cwd=out_dir, capture_output=True,
                       text=True, errors='replace', timeout=600)
    log_txt = ''
    if os.path.isfile(log_path):
        log_txt = io.open(log_path, encoding='utf-8', errors='replace').read()
    fatal = re.findall(r'^! .*$', log_txt, re.M)
    pdf = os.path.join(out_dir, stem + '.pdf')
    return len(fatal) == 0 and os.path.isfile(pdf), fatal, log_path


def main():
    ap = argparse.ArgumentParser(
        description='以新版 tex 为底，标红新增/改动，并展开交叉引用为纯文本（v0.20）')
    ap.add_argument('old', help='旧版本 tex 路径')
    ap.add_argument('new', help='新版本 tex 路径')
    ap.add_argument('out_dir', help='输出 marked-up 文件夹路径')
    ap.add_argument('--name', default='marked-up maintext')
    ap.add_argument('--compile', action='store_true')
    args = ap.parse_args()

    if not os.path.isfile(args.old):
        sys.exit('[ERR] 旧版 tex 不存在: %s' % args.old)
    if not os.path.isfile(args.new):
        sys.exit('[ERR] 新版 tex 不存在: %s' % args.new)

    src_dir = os.path.dirname(os.path.abspath(args.new))
    new_stem = os.path.splitext(os.path.basename(args.new))[0]

    print('[1/4] expand \\ref / \\eqref / \\cite to plain text')
    old_text = io.open(args.old, encoding='utf-8', newline='').read()
    new_text = io.open(args.new, encoding='utf-8', newline='').read()

    aux_path = os.path.join(src_dir, new_stem + '.aux')
    bbl_path = None
    for cand in (os.path.join(src_dir, new_stem + '.bbl'),
                 os.path.join(src_dir, 'maintext.bbl')):
        if os.path.isfile(cand):
            bbl_path = cand
            break
    label_map, cite_map = read_aux(aux_path)
    if not label_map:
        label_map = scan_labels_from_tex(new_text)
        print('      [info] .aux not found, scanned labels from tex: %d entries'
              % len(label_map))
    print('      label_map entries: %d, cite_map entries: %d'
          % (len(label_map), len(cite_map)))

    # 先对新旧两个版本都展开引用，再做 diff，避免展开后重复
    old_text = expand_refs(old_text, label_map, cite_map)
    new_text = expand_refs(new_text, label_map, cite_map)

    if bbl_path:
        bbl = io.open(bbl_path, encoding='utf-8', errors='replace').read().strip()
        old_text = re.sub(r'\\bibliography\{[^}]*\}', lambda m: bbl, old_text)
        new_text = re.sub(r'\\bibliography\{[^}]*\}', lambda m: bbl, new_text)
        print('      bibliography expanded from .bbl')

    print('[2/4] diff  %s  ->  %s'
          % (os.path.basename(args.old), os.path.basename(args.new)))
    marked = diff_to_marked(old_text, new_text)

    os.makedirs(args.out_dir, exist_ok=True)
    out_tex = os.path.join(args.out_dir, args.name + '.tex')
    with io.open(out_tex, 'w', encoding='utf-8', newline='') as f:
        f.write(marked)
    print('      wrote %s  (%d chars)' % (out_tex, len(marked)))

    print('[3/4] copy dependencies')
    copied = copy_dependencies(args.new, args.out_dir, args.name)
    print('      .bbl copied: %s' % ('yes' if copied else 'NO'))

    if not args.compile:
        print('[4/4] done. 打开 TeXstudio 编译 %s.tex 即可。' % args.name)
        return
    print('[4/4] auto-compile')
    ok, fatal, log_path = compile_pdf(args.out_dir, args.name)
    if not ok:
        print('[!!] compile failed; see %s' % log_path)
        for e in fatal[:15]:
            print('     ' + e)
        sys.exit(1)
    print('      PDF OK.')


if __name__ == '__main__':
    main()
