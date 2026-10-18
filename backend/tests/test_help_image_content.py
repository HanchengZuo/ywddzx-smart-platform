from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest

from help_documents import normalize_content, serialize
from help_image_content import IMAGE_PREFIX, inline_content, image_nodes


class InlineHelpImageTests(unittest.TestCase):
    def figure(self, **overrides):
        return IMAGE_PREFIX + json.dumps(dict(id='inspection-workflow', caption='流程图', width=100, **overrides))

    def test_legacy_images_become_inline_and_are_not_duplicated_or_written_back(self):
        original = {'body': '前面的操作说明', 'attachments': ['inspection-workflow', 'issue-appeal-workflow']}
        snapshot = deepcopy(original)
        result = inline_content(original)
        self.assertEqual([node['id'] for node in image_nodes(result['body'])], original['attachments'])
        self.assertEqual(result['attachments'], [])
        self.assertEqual(inline_content(result), result)
        self.assertEqual(original, snapshot)

    def test_existing_image_keeps_its_position_and_caption(self):
        body = '上文\n' + self.figure() + '\n下文'
        result = inline_content({'body': body, 'attachments': ['inspection-workflow']})
        self.assertEqual(result['body'], body)
        self.assertEqual(len(image_nodes(result['body'])), 1)

    def test_caption_width_source_and_image_count_are_validated(self):
        invalid = [dict(id='https://evil.example/image.png'), dict(id='../../secret'), dict(width=999),
                   dict(width=True), dict(caption=['invalid']), dict(caption='x' * 161), dict(src='data:image/png;base64,x')]
        for overrides in invalid:
            node = dict(id='inspection-workflow', caption='流程图', width=100)
            node.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                image_nodes(IMAGE_PREFIX + json.dumps(node))
        for body in ['::help-image invalid', '::help-image []', '\n'.join([self.figure()] * 13)]:
            with self.assertRaises(ValueError):
                image_nodes(body)

    def test_published_and_draft_figures_stay_separate_without_changing_metadata(self):
        now = datetime.now(timezone.utc)
        row = dict(id='example', revision=7, archived=False, updated_by_name='编辑者', updated_at=now,
                   published_by_name='发布者', published_at=now,
                   published=dict(body='已发布说明', attachments=['inspection-workflow']),
                   draft=dict(body='秘密草稿', attachments=['issue-appeal-workflow']))
        original = deepcopy(row)
        reader = serialize(row)
        editor = serialize(row, True)
        self.assertEqual(image_nodes(reader['content']['body'])[0]['id'], 'inspection-workflow')
        self.assertNotIn('秘密草稿', json.dumps(reader, ensure_ascii=False))
        self.assertEqual(image_nodes(editor['content']['body'])[0]['id'], 'issue-appeal-workflow')
        self.assertEqual(reader['revision'], 7)
        self.assertEqual(reader['updated_by'], '发布者')
        self.assertEqual(row, original)

    def test_saving_persists_inline_body_and_no_longer_stores_reference_list(self):
        result = normalize_content(dict(title='使用指南', category='新手上手', summary='', tags=[],
            body='填写表单后提交。', attachments=['inspection-workflow']))
        self.assertEqual(result['attachments'], [])
        self.assertEqual(len(image_nodes(result['body'])), 1)


if __name__ == '__main__':
    unittest.main()
