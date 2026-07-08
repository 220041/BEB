#!/usr/bin/env python3
"""5개 과목 .md 파일을 파싱해 all_data.json 생성"""
import re, json
from pathlib import Path

CIRCLE_TO_NUM = {'①': 1, '②': 2, '③': 3, '④': 4}

SUBJECTS = [
    {'file': '/mnt/project/01_의료기기_기초의학_clean.md',  'name': '의료기기 기초의학',  'short': '기초의학',  'color': '#2563EB'},
    {'file': '/mnt/project/02_의료기기_공학_clean.md',      'name': '의료기기 공학',      'short': '공학',      'color': '#7C3AED'},
    {'file': '/mnt/project/03_의료기기_구조원리_clean.md',  'name': '의료기기 구조원리',  'short': '구조원리',  'color': '#059669'},
    {'file': '/mnt/project/04_의료기기_인허가_clean.md',    'name': '의료기기 인허가',    'short': '인허가',    'color': '#D97706'},
    {'file': '/mnt/project/05_의료기기_관리_clean.md',      'name': '의료기기 관리',      'short': '관리',      'color': '#DC2626'},
]

# ── 파서 함수 ────────────────────────────────

def parse_metadata(text):
    meta = {}
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('-'):
            continue
        if ':' in line:
            key, _, val = line.partition(':')
            key, val = key.strip(), val.strip()
            if key:
                meta[key] = val
    return meta

def parse_flashcards(text):
    cards = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('- '):
            line = line[2:].strip()
        if '|' in line:
            q, _, a = line.partition('|')
            q, a = q.strip(), a.strip()
            if q and a:
                cards.append({'q': q, 'a': a})
    return cards

def parse_questions(text):
    questions = []
    blocks = re.split(r'(?=문제\s+\d+[\.\s])', text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m = re.match(r'문제\s+(\d+)[\.\s]\s*(.*?)(?=\n\s*[①②③④])', block, re.DOTALL)
        if not m:
            continue
        q_num  = int(m.group(1))
        q_text = re.sub(r'\n+', ' ', m.group(2)).strip()
        rest   = block[m.end():].strip()

        choices_end  = re.search(r'\n\s*정답:', rest)
        choices_text = rest[:choices_end.start()] if choices_end else rest

        choices = []
        for cm in re.finditer(r'[①②③④]\s*(.*?)(?=[①②③④]|\Z)', choices_text, re.DOTALL):
            ct = re.sub(r'\n+', ' ', cm.group(1)).strip()
            if ct:
                choices.append(ct)

        answer_m = re.search(r'정답:\s*([①②③④\d])', rest)
        answer = None
        if answer_m:
            ans = answer_m.group(1)
            answer = CIRCLE_TO_NUM.get(ans) or (int(ans) if ans in '1234' else None)

        exp_m = re.search(r'해설:\s*(.*?)$', rest, re.DOTALL)
        explanation = exp_m.group(1).strip() if exp_m else ''

        questions.append({
            'number': q_num,
            'text': q_text,
            'choices': choices,
            'answer': answer,
            'explanation': explanation
        })
    return questions

def parse_unit(unit_text, unit_id, subject, title):
    sec_pat = re.compile(r'\n### (\d+)\. (.+?)\n', re.MULTILINE)
    matches = list(sec_pat.finditer(unit_text))

    sections = {}
    for i, m in enumerate(matches):
        sec_num   = int(m.group(1))
        sec_title = m.group(2).strip()
        start = m.end()
        end   = matches[i+1].start() if i+1 < len(matches) else len(unit_text)
        sections[sec_num] = {'title': sec_title, 'content': unit_text[start:end].strip()}

    exam_tips = '\n\n'.join(
        f"### {sections[n]['title']}\n\n{sections[n]['content']}"
        for n in [5, 6] if n in sections
    )

    meta = parse_metadata(sections.get(9, {}).get('content', ''))

    return {
        'unit_id':      unit_id,
        'subject':      subject,
        'title':        title,
        'objectives':   sections.get(2, {}).get('content', ''),
        'concept':      sections.get(3, {}).get('content', ''),
        'memorization': sections.get(4, {}).get('content', ''),
        'exam_tips':    exam_tips,
        'questions':    parse_questions(sections.get(7, {}).get('content', '')),
        'flashcards':   parse_flashcards(sections.get(8, {}).get('content', '')),
        'chapter':      meta.get('chapter', ''),
        'section_name': meta.get('section', ''),
        'keywords':     [k.strip() for k in meta.get('keywords', '').split(',') if k.strip()],
        'priority':     meta.get('priority', '중'),
        'next_unit':    meta.get('next_unit', ''),
    }

def parse_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    units = []
    pat = re.compile(
        r'<!--BEGIN_UNIT id="([^"]+)" subject="([^"]+)" title="([^"]+)"-->(.*?)<!--END_UNIT-->',
        re.DOTALL
    )
    for m in pat.finditer(content):
        units.append(parse_unit(m.group(4), m.group(1), m.group(2), m.group(3)))
    return units

# ── 실행 ─────────────────────────────────────

all_data = {'subjects': []}
total_units = total_q = total_fc = 0

for subj in SUBJECTS:
    print(f"파싱 중: {subj['short']} ...", end=' ')
    units = parse_file(subj['file'])

    # 문제/플래시카드 수 검증
    bad_q  = [u for u in units if len(u['questions']) != 5]
    bad_fc = [u for u in units if len(u['flashcards']) == 0]

    if bad_q:
        print(f"\n  ⚠️  문제 수 이상: {[u['unit_id'] for u in bad_q]}")
    if bad_fc:
        print(f"\n  ⚠️  플래시카드 없음: {[u['unit_id'] for u in bad_fc]}")

    uq  = sum(len(u['questions'])  for u in units)
    ufc = sum(len(u['flashcards']) for u in units)
    print(f"{len(units)}단원 | 문제 {uq} | 플래시카드 {ufc}")

    all_data['subjects'].append({
        'name':   subj['name'],
        'short':  subj['short'],
        'color':  subj['color'],
        'units':  units,
    })
    total_units += len(units)
    total_q     += uq
    total_fc    += ufc

# 요약 통계 추가
all_data['summary'] = {
    'total_subjects': len(SUBJECTS),
    'total_units':    total_units,
    'total_questions': total_q,
    'total_flashcards': total_fc,
}

output = '/home/claude/all_data.json'
with open(output, 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, separators=(',', ':'))

size_kb = Path(output).stat().st_size // 1024
print(f"\n✅ all_data.json 생성 완료")
print(f"   단원: {total_units} | 문제: {total_q} | 플래시카드: {total_fc}")
print(f"   파일 크기: {size_kb} KB")
