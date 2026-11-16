from vdos import buffer_sync, captions


def test_map_words_across_cuts_and_speed():
    words = [{"w": "a", "s": 1.0, "e": 1.5}, {"w": "b", "s": 5.0, "e": 5.5}, {"w": "c", "s": 11.0, "e": 11.4}]
    out = captions.map_words(words, [(0.0, 2.0), (10.0, 12.0)], speed=2.0)
    assert [w["w"] for w in out] == ["a", "c"]          # "b" was cut
    assert out[0]["s"] == 0.5 and out[1]["s"] == (2.0 + 1.0) / 2.0


def test_ass_has_hook_and_words():
    ass = captions.build_ass([{"w": "hello", "s": 0.1, "e": 0.5}, {"w": "there", "s": 0.6, "e": 1.0}], 1080, 1920, "pop", "Hook!")
    assert "Hook!" in ass and "HELLO" in ass


def test_metric_parsing_shapes():
    assert buffer_sync._metric_values({"metrics": [{"type": "views", "value": 10}, {"type": "likes", "value": 2}]}) == {"views": 10.0, "likes": 2.0}
    assert buffer_sync._metric_values({"metrics": {"videoViews": 7, "shares": 1}}) == {"views": 7.0, "shares": 1.0}
