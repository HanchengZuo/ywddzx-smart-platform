"""Owned conversation ancestry in existing question JSON metadata, without new tables."""
import re
from expert_query import infer_options


def valid_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[a-f0-9]{32}', value))


def parent_row(cur, user_id, session_key, identifier):
    cur.execute('''SELECT id,question,options,result FROM expert_qa_questions
        WHERE id=%s AND user_id=%s AND session_key=%s AND status='completed' ''',
        [identifier, user_id, session_key])
    row = cur.fetchone()
    if not row:
        raise ValueError('追问对应的历史答案不可用，请新建问答。')
    return dict(row)


def parent_metadata(row):
    options = row.get('options') or {}
    root = options.get('conversation_id') or row['id']
    if not valid_id(root):
        raise ValueError('历史会话信息不正确，请新建问答。')
    return root


def load_context(cur, user_id, session_key, parent, limit=6):
    if not parent:
        return {}
    chain, seen = [], set()
    while parent and len(chain) < limit:
        if not valid_id(parent) or parent in seen:
            raise ValueError('历史会话信息不正确，请新建问答。')
        seen.add(parent)
        row = parent_row(cur, user_id, session_key, parent)
        chain.append(row)
        parent = (row.get('options') or {}).get('parent_id') or ''
    latest = chain[0]
    retrieval = (latest.get('result') or {}).get('retrieval') or {}
    if retrieval.get('scope_version') == 2:
        options = retrieval.get('options') or {}
    elif (latest.get('options') or {}).get('scope_version') == 2:
        options = latest['options']
    else:
        # Old UI-only filters are not silently inherited into the new all-data experience.
        options = infer_options(latest['question'])
    turns = []
    for row in reversed(chain):
        answer = (row.get('result') or {}).get('answer') or {}
        turns.append({'question': row['question'][:1500], 'answer': {
            'paragraphs': [{'text': str(part.get('text') or '')[:600]}
                           for part in answer.get('paragraphs', [])[:4]],
            'caveat': str(answer.get('caveat') or '')[:200],
        }})
    # No old S-identifiers are carried forward as valid citations for a new answer.
    return {'question': latest['question'], 'answer': turns[-1]['answer'], 'turns': turns,
            'options': options, 'conversation_id': parent_metadata(latest)}
