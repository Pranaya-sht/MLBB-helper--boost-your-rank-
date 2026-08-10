"""
Offline Ban / Pick / Win (BPW) meta analysis from tournament game CSVs.

Logic ported from data/mlbb_bpw_analysis.ipynb (no Colab / tqdm dependency).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA_DIR = os.path.join(ROOT, "data", "data-20260810T160518Z-1-001", "data")

EXPECTED_STAT_KEYS = [
    "hero_name",
    "num_games",
    "blue_ban_num",
    "red_ban_num",
    "full_ban_num",
    "full_ban_rate",
    "blue_ban_ratio",
    "red_ban_ratio",
    "mbat_team_name",
    "mbat_ban_num",
    "mbat_ban_ratio",
    "blue_pick_num",
    "blue_pick_rate",
    "red_pick_num",
    "red_pick_rate",
    "full_pick_num",
    "full_pick_rate",
    "mpnt_team_name",
    "mpnt_pick_num",
    "mpnt_win_num",
    "mpnt_win_rate",
    "full_bp_num",
    "full_bp_rate",
    "full_win_num",
    "full_lose_num",
    "full_win_rate",
    "full_win_avg_game_time_sec",
    "full_lose_avg_game_time_sec",
    "mwrt_team_name",
    "mwrt_pick_num",
    "mwrt_win_num",
    "mwrt_win_rate",
]


def adjust_hero_name(hero_name: str) -> str:
    return str(hero_name).strip().lower()


def display_hero_name(hero_name: str) -> str:
    return " ".join(str(hero_name).strip().split()).title()


def replace_error_date(date_str: Any) -> Optional[str]:
    text = str(date_str)
    if len(text) != 8:
        return None
    return text


def robust_division(numerator: float, denom: float, error_value: float = 0.0) -> float:
    if denom == 0:
        return error_value
    return numerator / denom


def convert_bp_str_to_list(bp_in_str: Any) -> List[str]:
    """Parse notebook-style pick/ban strings like ('Yu Zhong', 'Martis', ...)."""
    if isinstance(bp_in_str, (list, tuple)):
        return [adjust_hero_name(name) for name in bp_in_str if str(name).strip()]

    if bp_in_str is None or (isinstance(bp_in_str, float) and pd.isna(bp_in_str)):
        return []
    if isinstance(bp_in_str, str) is False and pd.isna(bp_in_str):
        return []

    text = str(bp_in_str).strip()
    if not text:
        return []

    if text[0] == "(" and text[-1] == ")":
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [name.strip("' ").lower() for name in inner.split(",")]

    # Fallback: comma-separated plain names
    return [name.strip("' ").lower() for name in text.split(",") if name.strip("' ")]


def check_ban_pick_result(
    hero_name: str,
    t1_name: str,
    t1_side: str,
    t1_bans: Sequence[str],
    t1_picks: Sequence[str],
    t1_result: Any,
    t2_name: str,
    t2_side: str,
    t2_bans: Sequence[str],
    t2_picks: Sequence[str],
    t2_result: Any,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Any]:
    if hero_name in t1_bans:
        ban_side = t1_side
        ban_against_team = t2_name
    elif hero_name in t2_bans:
        ban_side = t2_side
        ban_against_team = t1_name
    else:
        ban_side = None
        ban_against_team = None

    if hero_name in t1_picks:
        pick_side = t1_side
        pick_team = t1_name
        result = t1_result
    elif hero_name in t2_picks:
        pick_side = t2_side
        pick_team = t2_name
        result = t2_result
    else:
        pick_side = None
        pick_team = None
        result = None

    return ban_side, ban_against_team, pick_side, pick_team, result


def get_sides_bp_stats(bp_side_df: pd.DataFrame) -> Dict[str, int]:
    ban_counts = bp_side_df["ban_side"].value_counts()
    pick_counts = bp_side_df["pick_side"].value_counts()
    return {
        "blue_ban_num": int(ban_counts.get("blue", 0)),
        "blue_pick_num": int(pick_counts.get("blue", 0)),
        "red_ban_num": int(ban_counts.get("red", 0)),
        "red_pick_num": int(pick_counts.get("red", 0)),
    }


def get_win_lose_stats(res_gametime_df: pd.DataFrame) -> Dict[str, Any]:
    win_games_df = res_gametime_df[res_gametime_df["result"] == 1]
    win_num = int(win_games_df.shape[0])
    win_avg = win_games_df["game_time_sec"].mean()
    if pd.isna(win_avg):
        win_avg = 0

    lose_games_df = res_gametime_df[res_gametime_df["result"] == 0]
    lose_num = int(lose_games_df.shape[0])
    lose_avg = lose_games_df["game_time_sec"].mean()
    if pd.isna(lose_avg):
        lose_avg = 0

    return {
        "full_win_num": win_num,
        "full_lose_num": lose_num,
        "full_win_avg_game_time_sec": int(round(win_avg)),
        "full_lose_avg_game_time_sec": int(round(lose_avg)),
    }


def get_derived_stats(
    num_games: int, sides_bp_stats: Dict[str, int], win_lose_stats: Dict[str, Any]
) -> Dict[str, Any]:
    full_ban_num = sides_bp_stats["red_ban_num"] + sides_bp_stats["blue_ban_num"]
    full_ban_rate = robust_division(full_ban_num, num_games, 0)
    full_pick_num = sides_bp_stats["red_pick_num"] + sides_bp_stats["blue_pick_num"]
    full_pick_rate = robust_division(full_pick_num, num_games - full_ban_num, 0)
    full_bp_num = full_ban_num + full_pick_num
    full_bp_rate = robust_division(full_bp_num, num_games, 0)
    full_win_rate = robust_division(win_lose_stats["full_win_num"], full_pick_num, 0)

    blue_ban_ratio = robust_division(sides_bp_stats["blue_ban_num"], full_ban_num, 0)
    red_ban_ratio = robust_division(sides_bp_stats["red_ban_num"], full_ban_num, 0)
    blue_pick_rate = robust_division(
        sides_bp_stats["blue_pick_num"],
        num_games - full_ban_num - sides_bp_stats["red_pick_num"],
        0,
    )
    red_pick_rate = robust_division(
        sides_bp_stats["red_pick_num"],
        num_games - full_ban_num - sides_bp_stats["blue_pick_num"],
        0,
    )

    return {
        "blue_ban_ratio": round(blue_ban_ratio, 4),
        "red_ban_ratio": round(red_ban_ratio, 4),
        "blue_pick_rate": round(blue_pick_rate, 4),
        "red_pick_rate": round(red_pick_rate, 4),
        "full_ban_num": full_ban_num,
        "full_ban_rate": round(full_ban_rate, 4),
        "full_pick_num": full_pick_num,
        "full_pick_rate": round(full_pick_rate, 4),
        "full_bp_num": full_bp_num,
        "full_bp_rate": round(full_bp_rate, 4),
        "full_win_rate": round(full_win_rate, 4),
    }


def get_notable_teams_stats(expanded_game_data_df: pd.DataFrame) -> Dict[str, Any]:
    pick_games_df = expanded_game_data_df[expanded_game_data_df["pick_side"].notna()]
    pick_team_summary = pick_games_df.groupby("pick_team").agg(
        pick_num=("pick_team", "size"),
        win_num=("result", "sum"),
    )
    if pick_team_summary.empty:
        pick_notable = {
            "mpnt_team_name": "",
            "mpnt_pick_num": 0,
            "mpnt_win_num": 0,
            "mpnt_win_rate": 0,
            "mwrt_team_name": "",
            "mwrt_pick_num": 0,
            "mwrt_win_num": 0,
            "mwrt_win_rate": 0,
        }
    else:
        pick_team_summary = pick_team_summary.reset_index()
        pick_team_summary["win_rate"] = (
            pick_team_summary["win_num"] / pick_team_summary["pick_num"]
        )
        mpnt = pick_team_summary.sort_values(
            by=["pick_num", "win_rate"], ascending=False
        ).head(1)
        mwrt = pick_team_summary.sort_values(
            by=["win_rate", "pick_num"], ascending=False
        ).head(1)
        pick_notable = {
            "mpnt_team_name": mpnt["pick_team"].iloc[0],
            "mpnt_pick_num": int(mpnt["pick_num"].iloc[0]),
            "mpnt_win_num": int(mpnt["win_num"].iloc[0]),
            "mpnt_win_rate": round(float(mpnt["win_rate"].iloc[0]), 4),
            "mwrt_team_name": mwrt["pick_team"].iloc[0],
            "mwrt_pick_num": int(mwrt["pick_num"].iloc[0]),
            "mwrt_win_num": int(mwrt["win_num"].iloc[0]),
            "mwrt_win_rate": round(float(mwrt["win_rate"].iloc[0]), 4),
        }

    ban_games_df = expanded_game_data_df[expanded_game_data_df["ban_side"].notna()]
    ban_team_summary = ban_games_df.groupby("ban_against_team").agg(
        ban_num=("ban_against_team", "size"),
    )
    if ban_team_summary.empty:
        ban_notable = {"mbat_team_name": "", "mbat_ban_num": 0}
    else:
        ban_team_summary = ban_team_summary.reset_index()
        mbat = ban_team_summary.sort_values(by=["ban_num"], ascending=False).head(1)
        ban_notable = {
            "mbat_team_name": mbat["ban_against_team"].iloc[0],
            "mbat_ban_num": int(mbat["ban_num"].iloc[0]),
        }

    out: Dict[str, Any] = {}
    out.update(pick_notable)
    out.update(ban_notable)
    return out


def get_all_stats(num_games: int, expanded_game_data_df: pd.DataFrame) -> Dict[str, Any]:
    sides_bp_stats = get_sides_bp_stats(expanded_game_data_df[["ban_side", "pick_side"]])
    win_lose_stats = get_win_lose_stats(
        expanded_game_data_df[["result", "game_time_sec"]]
    )
    derived_stats = get_derived_stats(num_games, sides_bp_stats, win_lose_stats)
    notable_team_stats = get_notable_teams_stats(expanded_game_data_df)
    mbat_ban_ratio = robust_division(
        notable_team_stats["mbat_ban_num"], derived_stats["full_ban_num"], 0
    )

    all_stats: Dict[str, Any] = {"mbat_ban_ratio": round(mbat_ban_ratio, 4)}
    all_stats.update(sides_bp_stats)
    all_stats.update(win_lose_stats)
    all_stats.update(derived_stats)
    all_stats.update(notable_team_stats)
    return all_stats


class MetaAnalyzer:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.hero_info_df: pd.DataFrame = pd.DataFrame()
        self.tournament_data_df: pd.DataFrame = pd.DataFrame()
        self.game_data_df: pd.DataFrame = pd.DataFrame()
        self._load()

    def _path(self, name: str) -> str:
        return os.path.join(self.data_dir, name)

    def _load(self) -> None:
        hero_path = self._path("hero_info.csv")
        tournament_path = self._path("tournament_data.csv")
        game_path = self._path("consolidated_game_data.csv")

        if not os.path.exists(hero_path):
            raise FileNotFoundError(f"Missing hero info CSV: {hero_path}")
        if not os.path.exists(tournament_path):
            raise FileNotFoundError(f"Missing tournament CSV: {tournament_path}")
        if not os.path.exists(game_path):
            raise FileNotFoundError(f"Missing game data CSV: {game_path}")

        hero_info_df = pd.read_csv(hero_path, usecols=["Name", "Hero Code"])
        hero_info_df["Name"] = hero_info_df["Name"].apply(adjust_hero_name)
        self.hero_info_df = hero_info_df

        tournament_data_df = pd.read_csv(tournament_path, dtype=str)
        tournament_data_df["start_date"] = tournament_data_df["start_date"].apply(
            replace_error_date
        )
        tournament_data_df["start_date"] = pd.to_datetime(
            tournament_data_df["start_date"], format="%Y%m%d", errors="coerce"
        )
        tournament_data_df["end_date"] = tournament_data_df["end_date"].apply(
            replace_error_date
        )
        tournament_data_df["end_date"] = pd.to_datetime(
            tournament_data_df["end_date"], format="%Y%m%d", errors="coerce"
        )
        self.tournament_data_df = tournament_data_df

        game_data_df = pd.read_csv(
            game_path,
            dtype={"tournament_code": str, "date": str, "game_time_str": str},
        )
        for col in ("t1_picks", "t1_bans", "t2_picks", "t2_bans"):
            game_data_df[col] = game_data_df[col].apply(convert_bp_str_to_list)
        self.game_data_df = game_data_df

    def list_tournaments(self) -> pd.DataFrame:
        cols = [
            "tournament_code",
            "tournament_name",
            "tier",
            "start_date",
            "end_date",
            "patch_code",
        ]
        return self.tournament_data_df[cols].copy()

    def filter_games(
        self,
        tournament_codes: Optional[Sequence[Any]] = None,
        tournament_tiers: Optional[Sequence[str]] = None,
        tournament_stages: Optional[str] = "b",
        tournament_start_date: Optional[int] = None,
        tournament_end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        filter_condition_list = []
        tdf = self.tournament_data_df

        if tournament_codes is not None:
            codes = [str(code) for code in tournament_codes]
            filter_condition_list.append(tdf["tournament_code"].isin(codes))

        if tournament_tiers is not None:
            filter_condition_list.append(tdf["tier"].isin(list(tournament_tiers)))

        if tournament_start_date is not None:
            start_dt = pd.to_datetime(tournament_start_date, format="%Y%m%d")
            filter_condition_list.append(tdf["start_date"] >= start_dt)

        if tournament_end_date is not None:
            end_dt = pd.to_datetime(tournament_end_date, format="%Y%m%d")
            filter_condition_list.append(tdf["end_date"] <= end_dt)

        combined = pd.Series([True] * len(tdf), index=tdf.index)
        for condition in filter_condition_list:
            combined = combined & condition

        filtered_tournaments = tdf[combined]
        updated_codes = filtered_tournaments["tournament_code"].tolist()
        code_condition = self.game_data_df["tournament_code"].isin(updated_codes)

        if tournament_stages == "b":
            stage_condition = self.game_data_df["tournament_stage"] == "bracket"
        else:
            stage_condition = pd.Series(
                [True] * len(self.game_data_df), index=self.game_data_df.index
            )

        return self.game_data_df[code_condition & stage_condition].copy()

    def compute_bpw_table(self, filtered_game_data_df: pd.DataFrame) -> pd.DataFrame:
        if filtered_game_data_df.empty:
            return pd.DataFrame(columns=EXPECTED_STAT_KEYS)

        num_games = int(filtered_game_data_df.shape[0])
        stats_dict_list: List[Dict[str, Any]] = []

        for _, row in self.hero_info_df.iterrows():
            hero_name = row["Name"]
            temp = filtered_game_data_df.copy(deep=True)
            temp[["ban_side", "ban_against_team", "pick_side", "pick_team", "result"]] = (
                temp.apply(
                    lambda r: check_ban_pick_result(
                        hero_name,
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
            )
            all_stats = get_all_stats(num_games, temp)
            final_dict = {
                "hero_name": display_hero_name(hero_name),
                "num_games": num_games,
            }
            final_dict.update(all_stats)
            stats_dict_list.append(final_dict)

        full_stats_df = pd.DataFrame(stats_dict_list)
        full_stats_df.sort_values(
            by=["full_bp_rate", "full_ban_rate", "full_win_rate"],
            ascending=False,
            inplace=True,
        )
        return full_stats_df[EXPECTED_STAT_KEYS]

    def analyze(
        self,
        tournament_codes: Optional[Sequence[Any]] = None,
        tournament_tiers: Optional[Sequence[str]] = None,
        tournament_stages: Optional[str] = "b",
        tournament_start_date: Optional[int] = None,
        tournament_end_date: Optional[int] = None,
    ) -> Dict[str, Any]:
        filtered = self.filter_games(
            tournament_codes=tournament_codes,
            tournament_tiers=tournament_tiers,
            tournament_stages=tournament_stages,
            tournament_start_date=tournament_start_date,
            tournament_end_date=tournament_end_date,
        )
        table = self.compute_bpw_table(filtered)
        return {
            "num_games": int(filtered.shape[0]),
            "table": table,
        }
