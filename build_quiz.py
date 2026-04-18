"""総務昼 問題集パーサ: raw JSON → quiz.json"""
import json, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(r'C:/Users/teemo/PycharmProjects/flash')

docx = json.load(open(ROOT / 'soumu_raw_docx.json', encoding='utf-8'))
doc  = json.load(open(ROOT / 'soumu_raw_doc.json', encoding='utf-8'))
ALL = {**docx, **doc}

# --- chapter mapping: chapter_key -> (問題file, 解答file) ---
def find_file(pattern):
    for k in ALL:
        if re.search(pattern, k):
            return k
    return None

CHAPTERS = [
    ('地公法1',  '地公法.?1問題',  '地公法.?1解答'),
    ('地公法2',  '地公法.?2問題',  '地公法.?2解答'),
    ('地公法3',  '地公法.?3問題',  '地公法.?3解答'),
    ('地公法4',  '地公法.?4問題',  '地公法.?4解答'),
    ('地公法5',  '地公法.?5問題',  '地公法.?5解答'),
    ('地公法6',  '地公法.?6問題',  '地公法.?6(解|回)答'),
    ('地公法総合','地公法総合問題','地公法総合解答'),
    ('自治法1',  '自治法.?1問題',  '自治法.?1解答'),
    ('自治法2',  '自治法.?2問題',  '自治法.?2解答'),
    ('自治法3',  '自治法.?3問題',  '自治法.?3解答'),
    ('自治法4',  '自治法.?4問題',  '自治法.?4解答'),
    ('自治法5',  '自治法.?5問題',  '自治法.?5解答'),
    ('自治法総合','自治法総合問題','自治法総合解答'),
    ('法律総合1','法律総合.?1問題','法律総合.?1解答'),
    ('法律総合2','法律総合.?2問題','法律総合.?2解答'),
]

# 全角→半角数字（①②③④⑤⑥⑦⑧⑨⑩も）
CIRC = {'①':'1','②':'2','③':'3','④':'4','⑤':'5','⑥':'6','⑦':'7','⑧':'8','⑨':'9','⑩':'10'}
def norm_num_str(s):
    for k,v in CIRC.items(): s = s.replace(k,v)
    s = s.translate(str.maketrans('０１２３４５６７８９','0123456789'))
    return s

def clean_line(s):
    """asposeのdoc変換ゴミ(□)を除去。□は区切り記号として使われてるだけ"""
    return s.replace('\u25a1', ' ').replace('\ufeff','').rstrip('\r')

def find_with_norm(pattern):
    """ファイルキーを正規化してマッチ"""
    for k in ALL:
        nk = norm_num_str(k)
        if re.search(pattern, nk):
            return k
    return None

def strip_head(s):
    """全角空白・半角空白の除去"""
    return s.replace('\u3000','').replace(' ','').strip()

# --- 問題ファイル分割 ---
Q_HEAD = re.compile(r'【問(\d+)】')

def split_questions(lines):
    """行リストから {問番号: [行]} に分割。
    先頭に【問N】がなく『正解』で始まる解答ファイルは問1として扱う。"""
    result = {}
    cur = None
    buf = []
    for ln in lines:
        nln = norm_num_str(ln)
        m = Q_HEAD.search(nln)
        if m:
            if cur is not None:
                result[cur] = buf
            cur = int(m.group(1))
            buf = [ln]
        else:
            # ヘッダ未検出状態で『正解』が出たら問1とみなす
            if cur is None and '正解' in nln:
                cur = 1
                buf = [ln]
            elif cur is not None:
                buf.append(ln)
    if cur is not None:
        result[cur] = buf
    return result

# --- 選択肢行抽出（１.xxx　２.xxx…） ---
CHOICE_LINE = re.compile(r'(?:^|\s)1\s*[.．、]')

def parse_choices(text_lines):
    """最後にある『1. xxx  2. xxx  ...』形式の行から選択肢5つを抜き出す。
    見つからなければ None。
    問題本文は選択肢行より前の行を結合。"""
    # norm後で探す
    for i in range(len(text_lines)-1, -1, -1):
        ln = text_lines[i]
        nln = norm_num_str(ln)
        # 「1.xxx 2.xxx 3.xxx 4.xxx 5.xxx」 or 「1xxx 2xxx…」
        # 条件: 1〜5の選択肢番号が全部含まれる
        if re.search(r'1[.．、]', nln) and re.search(r'2[.．、]', nln) and re.search(r'3[.．、]', nln) and re.search(r'4[.．、]', nln) and re.search(r'5[.．、]', nln):
            # 分割
            parts = re.split(r'([1-5])[.．、]', nln)
            # parts = ['', '1', 'xxx', '2', 'xxx', '3', 'xxx', '4', 'xxx', '5', 'xxx']
            choices = {}
            for j in range(1, len(parts)-1, 2):
                num = parts[j]
                val = parts[j+1].strip().replace('\u3000',' ').strip()
                choices[num] = val
            if all(k in choices for k in ['1','2','3','4','5']):
                body_lines = text_lines[:i]
                return [choices[str(k)] for k in range(1,6)], body_lines
    return None, text_lines

# --- 正解番号抽出 ---
ANS_RE = re.compile(r'正解\s*[\u3000 ]*(\d+)')

def parse_answer(lines):
    """解答行リスト → 正解番号（int）と解説全文。"""
    correct = None
    expl_lines = []
    for ln in lines:
        nln = norm_num_str(ln)
        m = ANS_RE.search(nln)
        if m and correct is None:
            correct = int(m.group(1))
        expl_lines.append(ln)
    # 解説は全文（正解行含む。ユーザー向けに参考になる）
    explanation = '\n'.join(l for l in expl_lines if l.strip())
    return correct, explanation

# --- メイン ---
chapters = []
report = []
for chap_name, q_pat, a_pat in CHAPTERS:
    q_file = find_with_norm(q_pat)
    a_file = find_with_norm(a_pat)
    if not q_file or not a_file:
        report.append(f'[MISSING] {chap_name}: q={q_file} a={a_file}')
        continue
    q_lines = [clean_line(l) for l in ALL[q_file]]
    a_lines = [clean_line(l) for l in ALL[a_file]]
    q_split = split_questions(q_lines)
    a_split = split_questions(a_lines)
    questions = []
    for qnum in sorted(q_split.keys()):
        qb = q_split[qnum]
        ab = a_split.get(qnum, [])
        # 問題本文と選択肢
        choices, body = parse_choices(qb)
        # 問題文テキストは body を改行結合、空行整理
        body_text = '\n'.join(l.rstrip() for l in body).strip()
        # 解答
        correct, expl = parse_answer(ab) if ab else (None, '')
        questions.append({
            'num': qnum,
            'body': body_text,
            'choices': choices,   # None になる場合あり（パース失敗時）
            'correct': correct,
            'explanation': expl,
        })
    chapters.append({'name': chap_name, 'questions': questions})
    ok_correct = sum(1 for q in questions if q['correct'])
    ok_choices = sum(1 for q in questions if q['choices'])
    report.append(f'[OK] {chap_name}: {len(questions)} questions, correct={ok_correct}, choices={ok_choices}')

print('\n'.join(report))
out = ROOT / 'quiz.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump({'chapters': chapters}, f, ensure_ascii=False, indent=1)
print(f'\nwrote: {out}')
