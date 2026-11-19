import unittest
from i18n import translate_text


class I18nRegressionTests(unittest.TestCase):
    def test_bilingual_language_caption_is_stable(self):
        value = '语言 / Language'
        for _ in range(200):
            value = translate_text(value, 'zh')
        self.assertEqual(value, '语言 / Language')

    def test_static_labels_translate_both_directions(self):
        self.assertEqual(translate_text('刷新串口', 'en'), 'Refresh Ports')
        self.assertEqual(translate_text('Refresh Ports', 'zh'), '刷新串口')

    def test_live_chinese_status_translates_without_mutating_source(self):
        source = '等待 MCU 查询结果；切换后需重新学习'
        english = translate_text(source, 'en')
        self.assertIn('MCU', english)
        self.assertIn('retraining', english)
        self.assertEqual(translate_text(source, 'zh'), source)


if __name__ == '__main__':
    unittest.main()
