import pandas as pd
import pytest

from core.meta_analyzer import (
    MetaAnalyzer,
    convert_bp_str_to_list,
    get_all_stats,
    check_ban_pick_result,
    EXPECTED_STAT_KEYS,
)


def test_convert_bp_str_to_list_tuple_string():
    raw = "('Yu Zhong', 'Martis', 'Faramis', 'Karrie', 'Mathilda')"
    names = convert_bp_str_to_list(raw)
    assert names == ["yu zhong", "martis", "faramis", "karrie", "mathilda"]


def test_convert_bp_str_to_list_empty_and_nan():
    assert convert_bp_str_to_list("()") == []
    assert convert_bp_str_to_list(pd.NA) == []
    assert convert_bp_str_to_list(["Tigreal", "Gusion"]) == ["tigreal", "gusion"]


def test_check_ban_pick_result_and_stats_keys():
    rows = [
        {
            "t1_name": "Alpha",
            "t1_side": "blue",
            "t1_bans": ["layla"],
            "t1_picks": ["tigreal", "gusion"],
            "t1_result": 1,
            "t2_name": "Beta",
            "t2_side": "red",
            "t2_bans": ["claude"],
            "t2_picks": ["esmeralda"],
            "t2_result": 0,
            "game_time_sec": 1200,
        },
        {
            "t1_name": "Alpha",
            "t1_side": "red",
            "t1_bans": ["esmeralda"],
            "t1_picks": ["layla"],
            "t1_result": 0,
            "t2_name": "Beta",
            "t2_side": "blue",
            "t2_bans": ["tigreal"],
            "t2_picks": ["gusion"],
            "t2_result": 1,
            "game_time_sec": 900,
        },
    ]
    df = pd.DataFrame(rows)
    df[["ban_side", "ban_against_team", "pick_side", "pick_team", "result"]] = df.apply(
        lambda r: check_ban_pick_result(
            "gusion",
            r["t1_name"],
            r["t1_side"],
            r["t1_bans"],
            r["t1_picks"],
            r["t1_result"],
            r["t2_name"],
            r["t2_side"],
            r["t2_bans"],
            r["t2_picks"],
            r["t2_result"],
        ),
        axis=1,
        result_type="expand",
    )
    stats = get_all_stats(num_games=2, expanded_game_data_df=df)
    assert stats["full_pick_num"] == 2
    assert 0 <= stats["full_ban_rate"] <= 1
    assert 0 <= stats["full_pick_rate"] <= 1
    assert 0 <= stats["full_win_rate"] <= 1
    assert 0 <= stats["full_bp_rate"] <= 1


def test_meta_analyzer_m5_bracket_smoke():
    analyzer = MetaAnalyzer()
    result = analyzer.analyze(
        tournament_codes=[1],
        tournament_tiers=None,
        tournament_stages="b",
        tournament_start_date=20230101,
        tournament_end_date=20231231,
    )
    assert result["num_games"] > 0
    table = result["table"]
    assert not table.empty
    for key in EXPECTED_STAT_KEYS:
        assert key in table.columns
    # Presence rates should be valid fractions
    assert (table["full_ban_rate"] >= 0).all() and (table["full_ban_rate"] <= 1).all()
    assert (table["full_win_rate"] >= 0).all() and (table["full_win_rate"] <= 1).all()
    # At least one hero should have been banned or picked in M5 bracket
    assert table["full_bp_num"].sum() > 0
