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


def test_labels():
    from vdos import labels
    assert labels.emoji_bucket("gotta walk 😭😭😭") == "3+" and labels.emoji_bucket("plain") == "0"
    assert labels.sound_type("alarm/firefighter-siren-deep__epidemic.mp3") == "siren"
    assert labels.sound_type("alarm/samsung-ringtone__voicemod.mp3") == "ringtone"
    assert labels.angle_of({"sus": True}) == "sus" and labels.angle_of({}) == "challenge"


def test_speed_tiers_cap_at_1_5():
    from vdos.variants import _speed_for
    vcfg = {"speed_tiers": [[15, [1.0, 1.05, 1.1]], [35, [1.2, 1.3, 1.4]], [9999, [1.3, 1.4, 1.5]]],
            "speed_levels": ["base", "faster", "fastest"], "speed_min": 1.0, "speed_max": 1.5}
    assert _speed_for(10, vcfg, None, "base") == 1.0
    assert _speed_for(60, vcfg, None, "fastest") == 1.5
    assert _speed_for(60, vcfg, 2.0, "base") == 1.5          # override still capped


def test_youtube_slots_two_of_four_rotate():
    from datetime import date
    from vdos.scheduler import _youtube_slots
    times = ["08:30", "12:00", "16:00", "19:30"]
    seen = set()
    for k in range(3):
        s = _youtube_slots(date(2026, 11, 22 + k), times, 2)
        assert len(s) == 2
        seen |= s
    assert seen == set(times)
