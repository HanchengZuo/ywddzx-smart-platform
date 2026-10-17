"""Bounded parent/child chunks and multi-channel lexical reciprocal-rank fusion."""
from collections import defaultdict
import re
from standard_retrieval import ALIASES, CatalogIndex, excerpt, tokens
from expert_query import explicit_issue_ids

CHUNK_SIZE = 1500
MAX_CHUNKS_PER_DOCUMENT = 72


def chunks(record, question=''):
    text = record['text']
    if len(text) <= CHUNK_SIZE:
        return [dict(record, parent_key=record['key'])]
    result = []
    for index, offset in enumerate(range(0, len(text), CHUNK_SIZE - 180)):
        if index >= MAX_CHUNKS_PER_DOCUMENT:
            break
        end = min(len(text), offset + CHUNK_SIZE)
        result.append(dict(record, key=f"{record['key']}:part:{index}", parent_key=record['key'],
                           text=text[offset:end], locator=f'正文第{offset + 1}至{end}字'))
    if question:
        stop = tokens('有什么哪些多少如何请问我们系统问题情况进行查询分析数据是否应该这个那个')
        terms = set(tokens(question)) - set(stop)
        for group in ALIASES:
            if any(term in question.lower() for term in group):
                terms.update(group)
        # Coarse local windows keep long files from building enormous token indexes.
        # Every extracted window is considered, but at most four enter fine reranking.
        result.sort(key=lambda row: (-sum(term in row['text'].lower() for term in terms), row['key']))
        return result[:4]
    return result


def ranked_chunks(question, records):
    candidates = [chunk for row in records for chunk in chunks(row, question)]
    if not candidates:
        return []
    indexes = [CatalogIndex(tuple((row['key'], row['title'], row['text']) for row in candidates)),
               CatalogIndex(tuple((row['key'], row['title'], row['kind']) for row in candidates))]
    scores = defaultdict(float)
    for weight, index in zip((1.0, .7), indexes):
        for rank, pos in enumerate(index.rank(question)[:240]):
            scores[pos] += weight / (60 + rank + 1)
    # ID requests are exact, not accidental substring matches in arbitrary descriptions.
    issue_ids = {str(value) for value in explicit_issue_ids(question)}
    standard_ids = set(re.findall(r'(?:规范|条款)\s*(?:ID|id|编号)?\s*[:：#]?\s*(\d+)', question))
    highlight_ids = set(re.findall(r'(?i)\bHL\s*(\d+)\b', question))
    for pos, row in enumerate(candidates):
        kind, _, identifier = row['parent_key'].partition(':')
        if identifier in {'issue': issue_ids, 'external': standard_ids, 'highlight': highlight_ids}.get(kind, set()):
            scores[pos] += 1
    order = sorted(scores, key=lambda pos: (-scores[pos], candidates[pos]['key']))
    result, parents, kinds, deferred = [], defaultdict(int), defaultdict(int), []
    for pos in order:
        row = candidates[pos]
        # Prevent a long original or a broad issue collection crowding out other sources.
        if parents[row['parent_key']] >= 2 or kinds[row['kind']] >= 8:
            deferred.append(row)
            continue
        result.append(row)
        parents[row['parent_key']] += 1
        kinds[row['kind']] += 1
    return result + deferred


def select_evidence(question, records, max_evidence=24, max_context=24000):
    unique = {row['key']: row for row in records}
    facts = [row for row in unique.values() if row['key'].startswith('stats:')]
    candidates = [row for row in unique.values() if not row['key'].startswith('stats:')]
    knowledge_only = re.search(r'规范|规定|要求|流程|权限|功能|怎么操作|如何操作', question) and not re.search(
        r'数量|多少|统计|分布|比例|占比|问题ID|问题编号|#\d|本月|上月|最近|进度|情况|哪些问题', question)
    if knowledge_only:
        # Unrelated live totals should not crowd out rules or invalidate a normative answer's cache.
        facts = [row for row in facts if row['key'] == 'stats:knowledge']
    # Exact full aggregates first. Do not make query-local snippets of a JSON count table.
    chosen = [dict(row, parent_key=row['key']) for row in facts] + ranked_chunks(question, candidates)
    result, remaining = [], max_context
    for row in chosen:
        if len(result) >= max_evidence or remaining < 500:
            break
        allowance = min(5000 if row['key'].startswith('stats:') else CHUNK_SIZE, remaining - len(row['title']) - 220)
        text = row['text']
        truncated = len(text) > allowance
        text = text[:allowance] if row['key'].startswith('stats:') else excerpt(text, question, allowance)
        if truncated and row['key'].startswith('stats:'):
            text = text[:max(0, allowance - 45)] + '\n【统计明细过长已截断，不可据片段推断未展示分组】'
        item = dict(row, text=text, id='S' + str(len(result) + 1))
        remaining -= len(text) + len(row['title']) + 200
        result.append(item)
    return result
