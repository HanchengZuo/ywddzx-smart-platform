"""Read-only local recall benchmark. Does not call AI or print issue descriptions.

Run from backend: python tools/benchmark_standard_retrieval.py
Historical references are weak labels, not verified relevance judgements.
"""
from pathlib import Path
import sys
import statistics
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from standard_retrieval import retrieve_standards, cached_index


def main():
    conn = app.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SET TRANSACTION READ ONLY')
        source = app.fetch_external_standard_map(cur)
        disabled = app.disabled_standard_ids(cur)
        source = {key: value for key, value in source.items() if key not in disabled}
        catalog = [dict(standard_id=str(key), inspection_table_name=value['inspection_table_name'],
                        detail_text=value['standard_detail_text']) for key, value in source.items()]
        cur.execute("SELECT standard_id,description FROM issues WHERE audit_status='approved' AND length(description)>10 AND standard_id IS NOT NULL ORDER BY id DESC LIMIT 1600")
        samples = {(r['standard_id'], r['description']) for r in cur.fetchall() if r['standard_id'] in source}
        hits = 0
        stats = []
        cached_index.cache_clear()
        for identifier, description in sorted(samples):
            candidates, meta = retrieve_standards(description, catalog)
            hits += str(identifier) in {row['standard_id'] for row in candidates}
            stats.append(meta)
        print(json.dumps({
            'samples': len(samples), 'catalog_count': len(catalog),
            'historical_id_recall': round(hits/len(samples), 4) if samples else None,
            'mean_candidates': round(statistics.mean(row['candidate_count'] for row in stats), 1) if stats else None,
            'mean_context_reduction_percent': round(statistics.mean(row['context_reduction_percent'] for row in stats), 1) if stats else None,
            'mean_retrieval_ms': round(statistics.mean(row['retrieval_ms'] for row in stats), 2) if stats else None,
            'note': 'Candidate recall only; not final AI recommendation accuracy. No AI calls.'
        }, ensure_ascii=False))
    finally:
        conn.rollback()
        conn.close()


if __name__ == '__main__':
    main()
