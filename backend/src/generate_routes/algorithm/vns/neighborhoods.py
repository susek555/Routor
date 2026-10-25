import logging
import random
from collections.abc import Callable
from dataclasses import dataclass

from src.generate_routes.algorithm.common_utils import haversine
from src.generate_routes.algorithm.vns.detour_sampler import DetourSampler
from src.generate_routes.algorithm.vns.vns_params import NeighborhoodParams
from src.generate_routes.data.map import Map

logger = logging.getLogger(__name__)

@dataclass
class OperatorStats:
    """Tracks invocation count and success rate for a neighborhood operator."""

    calls: int = 0
    improvements: int = 0

    @property
    def hit_rate(self) -> float:
        return (self.improvements / self.calls * 100.0) if self.calls > 0 else 0.0


class NeighborhoodOperator:
    """Executes shaking operators across configured neighborhood structures."""

    OPERATOR_NAMES = {
        1: "Biased Detour (Insert/Replace)",
        2: "Multi-Stage Expansion",
        3: "Ruin and Recreate",
        4: "Checkpoint Shift / Retract",
    }

    def __init__(
        self,
        params: NeighborhoodParams,
        sampler: DetourSampler,
        stage_graphs: list[Map],
        checkpoints: list[int],
        target_distance: float,
    ) -> None:
        self.params = params
        self.sampler = sampler
        self.stage_graphs = stage_graphs
        self.checkpoints = checkpoints
        self.target_distance = target_distance
        self.num_stages = len(checkpoints)

        self._stage_nodes_cache: list[list[int]] = [list(g.nodes()) for g in self.stage_graphs]
        self.stats: dict[int, OperatorStats] = {k: OperatorStats() for k in range(1, self.params.max_k + 1)}

        # Dispatch table mapping neighborhood index k to operator implementations
        self._operators: dict[int, Callable[[list[list[int]], int, float, list[int]], None]] = {
            1: self._op_biased_detour,
            2: self._op_multi_stage_expansion,
            3: self._op_ruin_and_recreate,
            4: self._op_checkpoint_shift,
        }

    def record_improvement(self, k: int) -> None:
        """Increments successful improvement counter for operator k."""
        self.stats[k].improvements += 1

    def _get_allowed_candidates(
        self,
        stage_idx: int,
        start_cp: int,
        dest_cp: int,
        existing_wps: set[int],
    ) -> list[int]:
        """Filters nodes outside the protected terminal zone and currently used waypoints."""
        stage_nodes = self._stage_nodes_cache[stage_idx]
        graph = self.stage_graphs[stage_idx]

        allowed = [
            n
            for n in stage_nodes
            if not self.sampler.is_in_terminal_zone(n, start_cp, dest_cp, graph) and n not in existing_wps
        ]
        return allowed if allowed else [n for n in stage_nodes if n not in existing_wps]

    def _op_biased_detour(
        self,
        wps: list[list[int]],
        stage_idx: int,
        needed_dist: float,
        allowed_cands: list[int],
    ) -> None:
        """k = 1: Biased Detour (Insert or Replace)."""
        max_allowed = self.params.max_detours_per_stage + 2
        graph = self.stage_graphs[stage_idx]

        if needed_dist > 0.0 and len(wps[stage_idx]) < max_allowed and allowed_cands:
            insert_pos = random.randint(1, len(wps[stage_idx]) - 1)  # noqa: S311
            u = wps[stage_idx][insert_pos - 1]
            w = wps[stage_idx][insert_pos]
            cand = self.sampler.select_biased_candidate(allowed_cands, u, w, graph, needed_dist)
            wps[stage_idx].insert(insert_pos, cand)
        elif len(wps[stage_idx]) > 2 and allowed_cands:  # noqa: PLR2004
            idx = random.randint(1, len(wps[stage_idx]) - 2)  # noqa: S311
            prev_n = wps[stage_idx][idx - 1]
            next_n = wps[stage_idx][idx + 1]
            wps[stage_idx][idx] = self.sampler.select_biased_candidate(
                allowed_cands, prev_n, next_n, graph, needed_dist
            )

    def _op_multi_stage_expansion(
        self,
        wps: list[list[int]],
        stage_idx: int,
        needed_dist: float,
        _allowed_cands: list[int],
    ) -> None:
        """k = 2: Multi-Stage Expansion (Stretch two consecutive stages)."""
        max_allowed = self.params.max_detours_per_stage + 2
        for offset in (0, 1):
            s_idx = (stage_idx + offset) % self.num_stages
            g_s = self.stage_graphs[s_idx]
            s_existing = set(wps[s_idx])
            s_allowed = self._get_allowed_candidates(s_idx, wps[s_idx][0], wps[s_idx][-1], s_existing)
            if s_allowed and len(wps[s_idx]) < max_allowed:
                ins_pos = random.randint(1, len(wps[s_idx]) - 1)  # noqa: S311
                u = wps[s_idx][ins_pos - 1]
                w = wps[s_idx][ins_pos]
                cand = self.sampler.select_biased_candidate(s_allowed, u, w, g_s, needed_dist / 2.0)
                wps[s_idx].insert(ins_pos, cand)

    def _op_ruin_and_recreate(
        self,
        wps: list[list[int]],
        stage_idx: int,
        needed_dist: float,
        allowed_cands: list[int],
    ) -> None:
        """k = 3: Ruin and Recreate (Reset stage to chord line and add fresh detour)."""
        start_cp, dest_cp = wps[stage_idx][0], wps[stage_idx][-1]
        wps[stage_idx] = [start_cp, dest_cp]
        clean_allowed = [n for n in allowed_cands if n not in (start_cp, dest_cp)]
        if needed_dist > 0.0 and clean_allowed:
            graph = self.stage_graphs[stage_idx]
            fresh_cand = self.sampler.select_biased_candidate(clean_allowed, start_cp, dest_cp, graph, needed_dist)
            wps[stage_idx].insert(1, fresh_cand)

    def _op_checkpoint_shift(
        self,
        wps: list[list[int]],
        _stage_idx: int,
        _needed_dist: float,
        _allowed_cands: list[int],
    ) -> None:
        """k = 4: Checkpoint Shift / Retract (Reposition stage junction node)."""
        if self.num_stages <= 1:
            return

        cp_idx_to_shift = random.randint(1, self.num_stages - 1)  # noqa: S311
        curr_cp_node = self.checkpoints[cp_idx_to_shift]
        g_curr = self.stage_graphs[cp_idx_to_shift]

        c_cp = self.sampler.get_coord(curr_cp_node, g_curr)
        other_cps = {self.checkpoints[i] for i in range(self.num_stages) if i != cp_idx_to_shift}
        local_candidates = [
            n
            for n in self._stage_nodes_cache[cp_idx_to_shift]
            if self.params.checkpoint_min_shift_distance_meters
            <= haversine(self.sampler.get_coord(n, g_curr), c_cp)
            <= self.params.checkpoint_shift_radius_meters
            and n not in other_cps
        ]

        if local_candidates:
            replacement_cp = random.choice(local_candidates)  # noqa: S311
            self.checkpoints[cp_idx_to_shift] = replacement_cp

            prev_stage = (cp_idx_to_shift - 1) % self.num_stages
            wps[prev_stage][-1] = replacement_cp
            wps[cp_idx_to_shift][0] = replacement_cp

    def shake(
        self,
        current_stage_wps: list[list[int]],
        k: int,
        current_dist: float,
    ) -> list[list[int]]:
        """Applies neighborhood perturbation k to the current waypoint configuration."""
        self.stats[k].calls += 1
        new_wps = [list(stage) for stage in current_stage_wps]
        needed_dist = max(0.0, self.target_distance - current_dist)

        stage_idx = random.randint(0, self.num_stages - 1)  # noqa: S311
        if not self._stage_nodes_cache[stage_idx]:
            return new_wps

        start_cp, dest_cp = new_wps[stage_idx][0], new_wps[stage_idx][-1]
        allowed_candidates = self._get_allowed_candidates(stage_idx, start_cp, dest_cp, set(new_wps[stage_idx]))

        operator_fn = self._operators.get(k)
        if operator_fn:
            operator_fn(new_wps, stage_idx, needed_dist, allowed_candidates)

        return new_wps

    def log_operator_stats(self) -> None:
        """Logs diagnostic summary of neighborhood operator invocations and success rates."""
        header_border = "=" * 70
        divider = "-" * 70

        lines = [
            f"\n{header_border}",
            "NEIGHBORHOOD OPERATOR PERFORMANCE SUMMARY (VNS)",
            header_border,
            f"{'k':<3} | {'Operator Name':<32} | {'Calls':<10} | {'Success':<8} | {'Hit Rate':<8}",
            divider,
        ]

        for k in range(1, self.params.max_k + 1):
            name = self.OPERATOR_NAMES.get(k, f"Neighborhood {k}")
            st = self.stats[k]
            lines.append(f"{k:<3} | {name:<32} | {st.calls:<10} | {st.improvements:<8} | {st.hit_rate:>6.1f}%")

        lines.append(f"{header_border}\n")
        logger.info("\n".join(lines))
