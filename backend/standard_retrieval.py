"""Local lexical RAG: Chinese n-gram BM25, domain expansion and bounded evidence.

Indexes are keyed by full catalog content, never by a stale time-only TTL.
No external service, model download or raw issue-description cache is required.
"""
from collections import Counter, defaultdict
from functools import lru_cache
import math
import re
import time

VERSION = 'lexical-rag-v1'
MAX_CANDIDATES = 48
MAX_GENERAL_CANDIDATES = 12
MAX_CONTEXT_CHARS = 16000
MAX_DETAIL_CHARS = 1800
ALIASES = (
    ('锈蚀', '生锈', '腐蚀'), ('接地', '静电'), ('盘盈', '盘亏', '盘点', '账实不符'),
    ('过期', '超保质期', '临期'), ('铅封', '封签', '企业封'), ('接卸', '卸油', '收油'),
    ('灭火器', '消防器材'), ('加油枪', '油枪'), ('未过机', '未入账', 'pos'),
    ('货架', '陈列', '商品摆放'), ('手机', '接打电话'), ('双报告', '质量验收'),
    ('先进先出', '最新日期', '旧货', '新货'), ('裸露线缆', '电线', '隔爆', '封堵'),
)


def tokens(text):
    text = str(text or '').lower()
    result = Counter(re.findall(r'[a-z0-9]+', text))
    for phrase in re.findall(r'[\u4e00-\u9fff]+', text):
        for size in (2, 3):
            result.update(phrase[i:i+size] for i in range(len(phrase)-size+1))
    return result


class CatalogIndex:
    def __init__(self, catalog):
        self.catalog = catalog
        self.postings = defaultdict(list)
        self.lengths = []
        for index, (_, table, detail) in enumerate(catalog):
            terms = tokens(table + '\n' + detail)
            self.lengths.append(sum(terms.values()))
            for term, frequency in terms.items():
                self.postings[term].append((index, frequency))
        self.average = sum(self.lengths) / max(1, len(catalog)) or 1
        self.general = [i for i, (_, _, detail) in enumerate(catalog)
                        if re.search(r'(?:检查内容|检查项目|检查主题|检查事项)：其他(?:\n|$|对生产经营)', detail)]

    def rank(self, description):
        query = {term: 1.0 for term in tokens(description)}
        for group in ALIASES:
            if any(term in description.lower() for term in group):
                for term in tokens(' '.join(group)):
                    query.setdefault(term, .25)
        scores = defaultdict(float)
        for term, weight in query.items():
            posting = self.postings.get(term, ())
            idf = math.log(1 + (len(self.catalog)-len(posting)+.5)/(len(posting)+.5))
            for index, frequency in posting:
                norm = 1.2 * (.25 + .75 * self.lengths[index]/self.average)
                scores[index] += weight * idf * frequency * 2.2 / (frequency + norm)
        # Only an explicitly mentioned complete ID is boosted, not a substring.
        mentioned = set(re.findall(r'(?<![a-z0-9])(?:[a-z]+)?\d+(?![a-z0-9])', description.lower()))
        for index, (identifier, _, _) in enumerate(self.catalog):
            if identifier.lower() in mentioned:
                scores[index] += 100
        return sorted(scores, key=lambda i: (-scores[i], self.catalog[i][0]))


@lru_cache(maxsize=4)
def cached_index(catalog):
    return CatalogIndex(catalog)


def excerpt(detail, query, limit):
    if len(detail) <= limit:
        return detail
    # Query-local windows retain relevant evidence even at the end of a long rule.
    width = min(360, max(40, limit-20))
    chunks = [(i, detail[i:i+width]) for i in range(0, len(detail), max(1, width-60))]
    query_terms = set(tokens(query))
    ranked = sorted(chunks, key=lambda part: (-len(set(tokens(part[1])) & query_terms), part[0]))
    selected = sorted(ranked[:max(1, (limit-20)//(width+3))])
    return ('【相关原文节选】\n' + '\n…\n'.join(text for _, text in selected))[:limit]


def retrieve_standards(description, standards, *, limit=MAX_CANDIDATES, history_ids=()):
    started = time.monotonic()
    catalog = tuple(sorted((str(row['standard_id']), str(row.get('inspection_table_name') or ''),
                            str(row.get('detail_text') or '')) for row in standards if row.get('standard_id')))
    index = cached_index(catalog)
    ranked = index.rank(description)
    if history_ids:
        positions = {row[0]: i for i, row in enumerate(catalog)}
        historical = list(dict.fromkeys(positions[key] for key in history_ids if key in positions))
        scores = defaultdict(float)
        for weight, order in ((1.0, ranked), (1.25, historical)):
            for rank, doc in enumerate(order):
                scores[doc] += weight/(60+rank+1)
        fused = sorted(scores, key=lambda doc: (-scores[doc], catalog[doc][0]))
        # Reserve evidence from both routes; history must not crowd out actual rules.
        ranked = list(dict.fromkeys(historical[:8] + ranked[:16] + fused))
    candidate_limit = max(1, min(int(limit), MAX_CANDIDATES))
    # No lexical evidence: don't send arbitrary records or the whole catalog to AI.
    selected = ranked[:candidate_limit]
    # Broad "other hazards" clauses lack lexical evidence. Keep them as explicitly
    # low-specificity alternatives; the model must prefer a concrete rule.
    if selected:
        selected += [i for i in index.general if i not in selected][:MAX_GENERAL_CANDIDATES]
    candidates = []
    remaining = MAX_CONTEXT_CHARS
    for offset, doc in enumerate(selected):
        identifier, table, detail = catalog[doc]
        allowance = min(MAX_DETAIL_CHARS, max(120, remaining // max(1, len(selected)-offset) - len(table)-len(identifier)-100))
        text = excerpt(detail, description, allowance)
        row = {'standard_id': identifier, 'inspection_table_name': table, 'detail_text': text}
        remaining -= len(identifier) + len(table) + len(text) + 100
        if remaining < 0:
            break
        candidates.append(row)
    original = sum(len(identifier)+len(table)+len(detail)+100 for identifier, table, detail in catalog)
    sent = MAX_CONTEXT_CHARS-remaining
    return candidates, {
        'method': 'history-rrf-v1' if history_ids else VERSION, 'catalog_count': len(catalog), 'candidate_count': len(candidates),
        'catalog_chars': original, 'candidate_chars': sent,
        'retrieval_ms': round((time.monotonic()-started)*1000, 2),
        'context_reduction_percent': round(100*(1-sent/original), 1) if original else 0,
    }
