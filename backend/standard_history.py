"""Scoped approved issue history for retrieval; historical text stays local."""
from collections import Counter, defaultdict
from functools import lru_cache
import math
import re
import unicodedata
from standard_retrieval import cached_index, tokens


def normalize_description(text):
    # Preserve punctuation, numbers and negation: '未核对' must never equal '已核对'.
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(text or '')).lower()).strip()


def fetch_standard_history(cur, user, mode, full_standards, scope_builder):
    scope, params = scope_builder(cur, user)
    where = list(scope)
    where += ["i.audit_status='approved'", "COALESCE(i.status,'') NOT IN ('已销毁','申诉中')",
              "length(trim(COALESCE(i.description,''))) >= 4"]
    column = 'internal_standard_id' if mode == 'internal' else 'standard_id'
    allowed = {str(row['standard_id']).upper() for row in full_standards}
    cur.execute(f'''SELECT i.id, i.{column} AS reference_id, i.description,
        i.station_id, i.inspection_id
      FROM issues i JOIN inspections ins ON ins.id=i.inspection_id
      JOIN stations s ON s.id=i.station_id
      WHERE {' AND '.join(where)} ORDER BY i.id''', params)
    return tuple((int(row['id']), str(row['reference_id']).upper(), normalize_description(row['description']),
                  int(row['station_id']), int(row['inspection_id']))
                 for row in cur.fetchall() if str(row['reference_id']).upper() in allowed)


class HistoryIndex:
    def __init__(self, history):
        self.exact = defaultdict(list)
        descriptions = defaultdict(set)
        for issue_id, standard_id, description, station_id, inspection_id in history:
            self.exact[description].append((issue_id, standard_id, station_id, inspection_id))
            descriptions[description].add(standard_id)
        # Duplicate descriptions don't multiply term frequency or popularity votes.
        self.documents = sorted(descriptions)
        self.references = [descriptions[description] for description in self.documents]
        raw = [Counter(tokens(description)) for description in self.documents]
        frequency = Counter(term for terms in raw for term in terms)
        self.idf = {term: math.log((1+len(raw))/(1+count))+1 for term, count in frequency.items()}
        self.postings = defaultdict(list)
        for i, terms in enumerate(raw):
            weights = {term: (1+math.log(count))*self.idf[term] for term, count in terms.items()}
            norm = math.sqrt(sum(value*value for value in weights.values())) or 1
            for term, weight in weights.items():
                self.postings[term].append((i, weight/norm))

    def search(self, description, standards):
        query = normalize_description(description)
        current = {str(row['standard_id']).upper(): row for row in standards}
        exact = [row for row in self.exact.get(query, []) if row[1] in current]
        ids = {row[1] for row in exact}
        stations = {row[2] for row in exact}
        inspections = {row[3] for row in exact}
        fast = None
        if len(query) >= 10 and len(ids) == 1 and len(stations) >= 3 and len(inspections) >= 3:
            identifier = next(iter(ids))
            detail = current[identifier].get('detail_text') or ''
            catalog = tuple(sorted((str(row['standard_id']).upper(), str(row.get('inspection_table_name') or ''),
                                    str(row.get('detail_text') or '')) for row in standards))
            lexical = cached_index(catalog).rank(description)
            corroborated = (identifier in {catalog[i][0] for i in lexical[:5]}
                            and len(set(tokens(query)) & set(tokens(detail))) >= 3)
            # Repeated human labels alone aren't ground truth. Require independent
            # evidence in current rules too, otherwise let AI compare candidates.
            if corroborated and not re.search(r'(?:检查内容|检查项目|检查主题|检查事项)：其他(?:\n|$|对生产经营)', detail):
                fast = {'standard_id': current[identifier]['standard_id'], 'confidence': '高',
                        'reason': f'相同描述在{len(stations)}个站点的已审核记录中引用一致，请确认适用性。'}
        terms = tokens(query)
        weights = {term: (1+math.log(count))*self.idf.get(term, 1) for term, count in terms.items()}
        norm = math.sqrt(sum(weight*weight for weight in weights.values())) or 1
        scores = defaultdict(float)
        for term, weight in weights.items():
            for i, value in self.postings.get(term, ()):
                scores[i] += weight/norm*value
        best = defaultdict(float)
        for i in sorted(scores, key=lambda i: (-scores[i], i))[:40]:
            if scores[i] < .18:
                continue
            for identifier in self.references[i]:
                if identifier in current:
                    best[identifier] = max(best[identifier], scores[i])
        # Conflicting exact references stay together as candidates, never auto-picked.
        for identifier in ids:
            best[identifier] = 1.0
        ranked = sorted(best, key=lambda identifier: (-best[identifier], identifier))[:24]
        return {'ranked_ids': [str(current[key]['standard_id']) for key in ranked], 'fast_recommendation': fast,
                'similarities': {str(current[key]['standard_id']): best[key] for key in ranked},
                'exact_count': len(exact), 'exact_conflict': len(ids) > 1,
                'top_similarity': round(max(best.values(), default=0), 4),
                'history_count': sum(len(rows) for rows in self.exact.values())}


@lru_cache(maxsize=2)
def cached_history_index(history):
    return HistoryIndex(history)


def match_history(description, standards, history):
    # Entire scoped row content is the key: edits, audit reversals and permission
    # changes cannot leave an old recommendation active until a TTL expires.
    return cached_history_index(tuple(sorted(history))).search(description, standards)


def recommend_from_history(description, standards, history):
    """Explicit manual assist: high-similarity history only, never an AI fallback."""
    result = match_history(description, standards, history)
    recommendations = []
    for identifier in result['ranked_ids']:
        similarity = result['similarities'][identifier]
        if similarity < .55:
            continue
        recommendations.append({
            'standard_id': identifier,
            'confidence': '高' if similarity >= .8 else '中',
            'reason': f'历史描述相似度约{round(min(1, similarity)*100)}%，仅供参考，请核对规范适用性。',
        })
        if len(recommendations) >= 6:
            break
    return {
        'generated': False, 'recommendation_source': 'local_history',
        'recommendations': recommendations, 'no_related': not recommendations,
        'message': '已从已审核问题中检索相似规范，未调用AI。请选择或继续手动搜索。' if recommendations
                   else '暂无足够相似的历史规范，请补充描述或继续手动搜索。未调用AI。',
    }
