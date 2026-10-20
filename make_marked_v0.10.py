# -*- coding: utf-8 -*-
"""
make_marked_v0.10.py — 在新版 tex 基础上，把"新增 / 改动"的文字标红，
其它格式、排版、行号、图注位置与新版 tex 完全一致。

用法:
    python make_marked_v0.10.py <old.tex> <new.tex> <out_dir> [--name STEM] [--compile]

参数:
    old.tex   旧版本 tex 的绝对/相对路径（只读）
    new.tex   新版本 tex 的绝对/相对路径（只读；输出 marked tex 以它为底）
    out_dir   输出 marked-up 文件夹路径（不存在则创建）
    --name    输出 tex 的文件名前缀（默认 = "marked-up maintext"）
    --compile 生成后自动用 pdflatex 编译两遍（默认关闭；推荐在 TeXstudio 里手动编译）

设计原则:
  1. 以 new.tex 为底：删除旧版内容不出现在输出里；新增/改动的片段只套一层
     \\textcolor{red}{...}，零宽度命令，不改变行号、换行位置、图注排版。
  2. 行级 diff -> 行内 token 级 diff；数学块、\\label/\\ref/\\cite/\\includegraphics
     等结构命令整体不标红，避免破坏 LaTeX 语法。
  3. `--` / `---` 作为原子 token，不会被拆成两个 `-` 分别标红。
  4. 相邻的红片段（含中间空格）后处理合并为一个 \\textcolor{red}{...}，
     避免 PDF 里出现颜色不一的"--"。
  5. 不修改 old.tex / new.tex / 任何源文件；只写 out_dir。
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
# 结构 / 元信息命令：即使内容变化也不标红（保护 LaTeX 结构）
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
             # v0.11: 表格环境整块保护，避免 & 和 \\ 被包进 \textcolor
             'tabular', 'tabular*', 'tabularx', 'tabulary', 'longtable',
             'threeparttable', 'threeparttablex', 'csvtable'}


def _cmd_name(text):
    m = re.match(r'(\\[A-Za-z]+\*?)', text)
    return m.group(1) if m else text


def tokenize_line(line):
    """把一行 LaTeX 切成 token 列表: (kind, text)。
    kind: CMD / MATH / BRACE / SPEC / SPACE / COMMENT / TXT
    v0.10: 连续 '-'（-- 或 ---）合并为一个 TXT token，避免 -- 被拆开标红。
    """
    toks = []
    n = len(line)
    i = 0
    while i < n:
        c = line[i]
        if c == '\\':
            j = i + 1
            # v0.11: \( ... \) 和 \[ ... \] 作为整体数学 token，不拆开
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
            # v0.10: 吞掉 -- 或 --- 作为一个原子 token
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
    """返回 (wrapped_text, should_red)。
    should_red=True 表示该 token 内容需要并入红块；False 表示原样输出。
    """
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
        return text, True   # 未排除的命令名：并入红块（通常是 caption 等内容命令外壳）
    if kind in ('MATH', 'MATHX'):
        return text, False
    if text == '' or text == '\n':
        return text, False
    return text, True


def try_expand_math(text):
    """把简单 $...$ 归一化为文本 token 参与匹配（格式等价 -> 不标红）。"""
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
# 后处理：把连续的"红 token 片段 + 中间空白"合并成一个 \textcolor{red}{...}
# ---------------------------------------------------------------------------
def merge_red_segments(chunks):
    """chunks: list of (text, is_red)。
    连续的 is_red=True 片段，以及它们之间的空格/tab（不含换行），
    合并成一个 \textcolor{red}{...}；换行、空行、非红非空白片段原样输出。
    v0.11: 红块遇到换行强制断开；flush 时检查花括号配对，不配对则不包。
    """
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

    def flush():
        nonlocal buf, buf_open
        if buf:
            content = ''.join(buf)
            # v0.11: 红块内不允许含换行（避免跨段落）
            if '\n' in content:
                # 按换行切开，逐段处理
                parts = content.split('\n')
                for idx, p in enumerate(parts):
                    if p.strip(' \t') and brace_balanced(p):
                        merged.append('\\textcolor{red}{' + p + '}')
                    else:
                        merged.append(p)
                    if idx < len(parts) - 1:
                        merged.append('\n')
            elif content.strip(' \t') and brace_balanced(content):
                merged.append('\\textcolor{red}{' + content + '}')
            else:
                merged.append(content)
            buf = []
            buf_open = False

    for text, is_red in chunks:
        if is_red:
            # v0.11: 如果 token 本身含换行，先 flush 当前 buf，再按行处理
            if '\n' in text:
                flush()
                # 把含换行的红 token 按行切，逐行包红
                parts = text.split('\n')
                for idx, p in enumerate(parts):
                    if p.strip(' \t') and brace_balanced(p):
                        merged.append('\\textcolor{red}{' + p + '}')
                    else:
                        merged.append(p)
                    if idx < len(parts) - 1:
                        merged.append('\n')
            else:
                buf.append(text)
                buf_open = True
        else:
            # 非红片段：只有空格/tab 可以并入红块；换行必须断开
            if buf_open and text and text.strip(' \t') == '' and '\n' not in text:
                buf.append(text)
            else:
                flush()
                merged.append(text)
    flush()
    return ''.join(merged)


def diff_to_marked(old_text, new_text):
    old_blocks, old_flags = merge_math_blocks(old_text.splitlines())
    new_blocks, new_flags = merge_math_blocks(new_text.splitlines())

    # chunks: [(text, is_red)] 全局累积
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

    # 截断到新版 \end{document}
    idx = result.find('\\end{document}')
    if idx != -1:
        eol = result.find('\n', idx)
        if eol != -1:
            result = result[:eol + 1]
    return result


def copy_dependencies(new_tex_path, out_dir, stem):
    """从 new.tex 所在目录复制编译依赖到 out_dir（只读源、写目标）。"""
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

    # 其它可能被 \input 的 .tex 片段（如 appendix 等）
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
    args = ['pdflatex', '-interaction=nonstopmode',
            os.path.basename(tex)]
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
        description='以新版 tex 为底，把新增/改动文字标红（v0.10）')
    ap.add_argument('old', help='旧版本 tex 路径')
    ap.add_argument('new', help='新版本 tex 路径')
    ap.add_argument('out_dir', help='输出 marked-up 文件夹路径')
    ap.add_argument('--name', default='marked-up maintext',
                    help='输出 tex 的文件名前缀（默认 "marked-up maintext"）')
    ap.add_argument('--compile', action='store_true',
                    help='生成后自动 pdflatex 编译两遍（默认不编译，推荐 TeXstudio 内编译）')
    args = ap.parse_args()

    if not os.path.isfile(args.old):
        sys.exit('[ERR] 旧版 tex 不存在: %s' % args.old)
    if not os.path.isfile(args.new):
        sys.exit('[ERR] 新版 tex 不存在: %s' % args.new)

    print('[1/3] diff  %s  ->  %s'
          % (os.path.basename(args.old), os.path.basename(args.new)))
    old_text = io.open(args.old, encoding='utf-8', newline='').read()
    new_text = io.open(args.new, encoding='utf-8', newline='').read()
    marked = diff_to_marked(old_text, new_text)

    os.makedirs(args.out_dir, exist_ok=True)
    out_tex = os.path.join(args.out_dir, args.name + '.tex')
    with io.open(out_tex, 'w', encoding='utf-8', newline='') as f:
        f.write(marked)
    print('      wrote %s  (%d chars)' % (out_tex, len(marked)))

    print('[2/3] copy dependencies (figure/, .cls/.bst/.bbl/.bib)')
    copied = copy_dependencies(args.new, args.out_dir, args.name)
    print('      .bbl copied: %s' % ('yes' if copied else 'NO'))

    if not args.compile:
        print('[3/3] done. 打开 TeXstudio 编译 %s.tex 即可。' % args.name)
        return

    print('[3/3] auto-compile with pdflatex x2')
    ok, fatal, log_path = compile_pdf(args.out_dir, args.name)
    if not ok:
        print('[!!] compile failed; see %s' % log_path)
        for e in fatal[:15]:
            print('     ' + e)
        sys.exit(1)
    print('      PDF OK.')


if __name__ == '__main__':
    main()
