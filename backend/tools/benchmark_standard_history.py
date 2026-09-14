"""Read-only time-split evaluation; no AI calls and no issue text output.

The final 800 rows are held out; only older approved rows enter the history index.
Historical labels can be inconsistent and are not expert relevance judgements.
"""
from pathlib import Path
import sys
import json
import statistics
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from standard_history import normalize_description, match_history
from standard_retrieval import retrieve_standards


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
        cur.execute("SELECT id,standard_id,description,station_id,inspection_id FROM issues WHERE audit_status='approved' AND status NOT IN ('已销毁','申诉中') AND length(trim(description))>=4 ORDER BY id")
        rows = [dict(row) for row in cur.fetchall() if row['standard_id'] in source]
        boundary = max(1, len(rows)-800)
        train, test = rows[:boundary], rows[boundary:]
        history = tuple((r['id'], str(r['standard_id']), normalize_description(r['description']), r['station_id'], r['inspection_id']) for r in train)
        baseline = enhanced = fast = fast_correct = 0
        times = []
        for row in test:
            original, _ = retrieve_standards(row['description'], catalog)
            baseline += str(row['standard_id']) in {item['standard_id'] for item in original}
            start = time.monotonic()
            experience = match_history(row['description'], catalog, history)
            candidates, _ = retrieve_standards(row['description'], catalog, history_ids=experience['ranked_ids'])
            times.append((time.monotonic()-start)*1000)
            enhanced += str(row['standard_id']) in {item['standard_id'] for item in candidates}
            if experience['fast_recommendation']:
                fast += 1
                fast_correct += str(row['standard_id']) == experience['fast_recommendation']['standard_id']
        print(json.dumps(dict(train=len(train), held_out=len(test), baseline_recall=baseline/max(1,len(test)),
            history_recall=enhanced/max(1,len(test)), no_ai_count=fast, no_ai_label_agreement=fast_correct/max(1,fast),
            mean_retrieval_ms=round(statistics.mean(times),2) if times else None,
            note='Temporal holdout, no AI calls; label agreement is not expert-verified accuracy.'), ensure_ascii=False))
    finally:
        conn.rollback()
        conn.close()


if __name__ == '__main__':
    main()
