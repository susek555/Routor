import logging
import math
import random
import networkx as nx

from src.generate_routes.algorithm.aco.evaluator import RouteEvaluator
from src.generate_routes.algorithm.aco.utils.common import get_node_coords, haversine
from src.generate_routes.algorithm.aco.utils.evaluator import EvaluationBreakdown
from src.generate_routes.algorithm.vns.vns_params import VNSParams
from src.generate_routes.data.map import Map

logger = logging.getLogger(__name__)


class VNSLoopGenerator:
    """Generuje pętlę biegową w architekturze VNS ze zwartą liczbą operatorów,
    ukierunkowaną losowością (Biased Randomization), korektą checkpointów,
    odpornym na rzadkie siatki (obszary wiejskie) fallbackiem topologicznym
    oraz post-processingiem wygładzającym niepotrzebne odnogi.
    """

    OPERATOR_NAMES = {
        1: "Biased Detour (Insert/Replace)",
        2: "Multi-Stage Expansion",
        3: "Ruin and Recreate",
        4: "Checkpoint Shift / Retract",
    }

    def __init__(
        self,
        params: VNSParams,
        checkpoints: list[int],
        stage_graphs: list[Map],
        evaluator: RouteEvaluator,
    ) -> None:
        self.params = params
        self.checkpoints = list(checkpoints)
        self.stage_graphs = stage_graphs
        self.evaluator = evaluator
        self.num_stages = len(checkpoints)

        # Cache współrzędnych
        self.node_coord_cache: dict[int, tuple[float, float]] = dict(self.evaluator.node_coord_cache)

        # Cache węzłów w poszczególnych podgrafach etapowych
        self._stage_nodes_cache: list[list[int]] = [list(g.nodes()) for g in self.stage_graphs]

        # Liczniki statystyk efektywności operatorów
        self.operator_stats = {k: {"calls": 0, "improvements": 0} for k in range(1, self.params.max_k + 1)}

    def _get_coord(self, node: int, graph: Map) -> tuple[float, float]:
        """Pobiera współrzędne węzła z cache lub wylicza je z grafu."""
        if node not in self.node_coord_cache:
            self.node_coord_cache[node] = get_node_coords(graph, node)
        return self.node_coord_cache[node]

    def _connect_stage(self, stage_idx: int, waypoints: list[int]) -> tuple[list[int], float]:
        """Łączy punkty etapu najkrótszymi ścieżkami z gwarantowanym, 4-stopniowym fallbackiem."""
        graph = self.stage_graphs[stage_idx]

        # --- POZIOM 1: Próba restrykcyjna (bez powtórzeń węzłów w etapie) ---
        strict_path, strict_dist = self._try_connect_stage(graph, waypoints, allow_overlap=False)
        if strict_path:
            return strict_path, strict_dist

        # --- POZIOM 2: Fallback łagodny (dozwolone przejście przez wspólne skrzyżowania/węzły) ---
        soft_path, soft_dist = self._try_connect_stage(graph, waypoints, allow_overlap=True)
        if soft_path:
            return soft_path, soft_dist

        # --- POZIOM 3: Fallback bazy (odrzucenie punktów pośrednich, ratowanie prostą bazą) ---
        base_waypoints = [waypoints[0], waypoints[-1]]
        fallback_path, fallback_dist = self._try_connect_stage(graph, base_waypoints, allow_overlap=True)
        if fallback_path:
            return fallback_path, fallback_dist

        # --- POZIOM 4: Fallback ostateczny (obszary wiejskie / zbyt ciasno wycięty podgraf) ---
        # Sięgamy po pełny, globalny graf mapy (z pierwszego etapu lub ewaluatora)
        try:
            full_graph = getattr(self.evaluator, "graph", self.stage_graphs[0])
            emergency_segment = nx.shortest_path(full_graph, source=waypoints[0], target=waypoints[-1], weight="length")
            emergency_dist = sum(
                self.evaluator.edge_info_cache.get((u, v), ([], 1.0))[1]
                for u, v in zip(emergency_segment[:-1], emergency_segment[1:], strict=False)
            )
            return emergency_segment, emergency_dist
        except (nx.NetworkXNoPath, nx.NodeNotFound, Exception):
            return [], 0.0

    def _try_connect_stage(self, graph: Map, waypoints: list[int], allow_overlap: bool) -> tuple[list[int], float]:
        """Próbuje połączyć zadaną listę waypoints Dijkstrą."""
        stage_path: list[int] = []
        stage_distance = 0.0
        visited_nodes: set[int] = set()

        for u, v in zip(waypoints[:-1], waypoints[1:], strict=False):
            if u == v:
                return [], 0.0

            try:
                segment = nx.shortest_path(graph, source=u, target=v, weight="length")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return [], 0.0

            if not allow_overlap:
                if any(node in visited_nodes for node in segment[1:]):
                    return [], 0.0

            for node in segment[1:]:
                visited_nodes.add(node)

            if not stage_path:
                visited_nodes.add(segment[0])
                stage_path.extend(segment)
            else:
                stage_path.extend(segment[1:])

            for src, dst in zip(segment[:-1], segment[1:], strict=False):
                _, edge_len = self.evaluator.edge_info_cache.get((src, dst), ([], 1.0))
                stage_distance += edge_len

        return stage_path, stage_distance

    def _evaluate_candidate_stages(self, stage_waypoint_lists: list[list[int]]) -> tuple[list[int], float, float]:
        """Skleja sekwencje etapów w jedną zamkniętą pętlę i liczy globalny fitness."""
        full_path: list[int] = []
        total_distance = 0.0

        for stage_idx in range(self.num_stages):
            sub_wps = stage_waypoint_lists[stage_idx]
            sub_path, sub_dist = self._connect_stage(stage_idx, sub_wps)

            if not sub_path:
                return [], 0.0, -1.0

            if not full_path:
                full_path.extend(sub_path)
            else:
                full_path.extend(sub_path[1:])
            total_distance += sub_dist

        fitness = self.evaluator.evaluate(full_path, total_distance=total_distance)
        return full_path, total_distance, fitness

    # --- GEOMETRIA I BIASED RANDOMIZATION ---

    def _is_in_terminal_zone(self, node: int, start_node: int, dest_node: int, graph: Map) -> bool:
        """Sprawdza, czy węzeł leży w strefie ochronnej startu LUB mety danego etapu."""
        c_node = self._get_coord(node, graph)
        c_start = self._get_coord(start_node, graph)
        c_dest = self._get_coord(dest_node, graph)

        in_start_zone = haversine(c_node, c_start) <= self.params.approach_lock_radius_meters
        in_dest_zone = haversine(c_node, c_dest) <= self.params.approach_lock_radius_meters

        return in_start_zone or in_dest_zone

    def _calculate_candidate_score(
        self,
        node: int,
        u: int,
        w: int,
        graph: Map,
        needed_distance: float,
    ) -> float:
        """Oblicza atrakcyjność węzła tranzytowego przy wstawieniu między u i w."""
        c_node = self._get_coord(node, graph)
        c_u = self._get_coord(u, graph)
        c_w = self._get_coord(w, graph)

        dist_u_node = haversine(c_u, c_node)
        dist_node_w = haversine(c_node, c_w)
        direct_dist = max(haversine(c_u, c_w), 1.0)

        detour_cost = (dist_u_node + dist_node_w) - direct_dist

        s = (dist_u_node + dist_node_w + direct_dist) / 2.0
        area_sq = max(0.0, s * (s - dist_u_node) * (s - dist_node_w) * (s - direct_dist))
        lateral_height = (2.0 * math.sqrt(area_sq)) / direct_dist

        lateral_score = min(3.5, (lateral_height / self.params.lateral_scale_meters) * self.params.lateral_bonus_weight)

        if needed_distance > 0:
            diff = abs(detour_cost - needed_distance)
            fit_score = 1.0 / (1.0 + (diff / 250.0) * self.params.distance_fit_weight)
        else:
            fit_score = 1.0 / (1.0 + (detour_cost / 150.0))

        return float(self.params.epsilon_weight + lateral_score + fit_score)

    def _select_biased_candidate(
        self,
        allowed_candidates: list[int],
        u: int,
        w: int,
        graph: Map,
        needed_distance: float,
    ) -> int:
        """Wybiera kandydata za pomocą ruletki prawdopodobieństwa (Biased Randomization)."""
        if not allowed_candidates:
            return u

        sample_pool = (
            random.sample(allowed_candidates, min(len(allowed_candidates), 40))
            if len(allowed_candidates) > 40
            else allowed_candidates
        )

        weights = [self._calculate_candidate_score(n, u, w, graph, needed_distance) for n in sample_pool]
        return random.choices(sample_pool, weights=weights, k=1)[0]

    # --- STRUKTURY SĄSIEDZTWA (4 VNS NEIGHBORHOODS) ---

    def _shake(self, current_stage_wps: list[list[int]], k: int, current_dist: float) -> list[list[int]]:
        """Aplikuje jedną z 4 struktur sąsiedztwa w zależności od stopnia perturbacji k."""
        self.operator_stats[k]["calls"] += 1
        new_wps = [list(stage) for stage in current_stage_wps]
        needed_dist = max(0.0, self.params.target_distance - current_dist)

        stage_idx = random.randint(0, self.num_stages - 1)
        stage_nodes = self._stage_nodes_cache[stage_idx]
        start_cp = new_wps[stage_idx][0]
        dest_cp = new_wps[stage_idx][-1]
        graph = self.stage_graphs[stage_idx]

        if not stage_nodes:
            return new_wps

        existing_stage_wps = set(new_wps[stage_idx])
        allowed_candidates = [
            n
            for n in stage_nodes
            if not self._is_in_terminal_zone(n, start_cp, dest_cp, graph) and n not in existing_stage_wps
        ]
        if not allowed_candidates:
            allowed_candidates = [n for n in stage_nodes if n not in existing_stage_wps]

        # -------------------------------------------------------------
        # k = 1: Biased Detour (Insert lub Replace)
        # -------------------------------------------------------------
        if k == 1:
            max_allowed_wps = self.params.max_detours_per_stage + 2
            if (
                current_dist < self.params.target_distance
                and len(new_wps[stage_idx]) < max_allowed_wps
                and allowed_candidates
            ):
                insert_pos = random.randint(1, len(new_wps[stage_idx]) - 1)
                u = new_wps[stage_idx][insert_pos - 1]
                w = new_wps[stage_idx][insert_pos]
                cand = self._select_biased_candidate(allowed_candidates, u, w, graph, needed_dist)
                new_wps[stage_idx].insert(insert_pos, cand)
            elif len(new_wps[stage_idx]) > 2 and allowed_candidates:
                idx = random.randint(1, len(new_wps[stage_idx]) - 2)
                prev_n = new_wps[stage_idx][idx - 1]
                next_n = new_wps[stage_idx][idx + 1]
                new_wps[stage_idx][idx] = self._select_biased_candidate(
                    allowed_candidates, prev_n, next_n, graph, needed_dist
                )

        # -------------------------------------------------------------
        # k = 2: Multi-Stage Expansion (Równoległe rozciągnięcie dwóch etapów)
        # -------------------------------------------------------------
        elif k == 2:
            max_allowed_wps = self.params.max_detours_per_stage + 2
            for offset in (0, 1):
                s_idx = (stage_idx + offset) % self.num_stages
                g_s = self.stage_graphs[s_idx]
                s_existing = set(new_wps[s_idx])
                s_allowed = [
                    n
                    for n in self._stage_nodes_cache[s_idx]
                    if not self._is_in_terminal_zone(n, new_wps[s_idx][0], new_wps[s_idx][-1], g_s)
                    and n not in s_existing
                ]
                if s_allowed and len(new_wps[s_idx]) < max_allowed_wps:
                    ins_pos = random.randint(1, len(new_wps[s_idx]) - 1)
                    u = new_wps[s_idx][ins_pos - 1]
                    w = new_wps[s_idx][ins_pos]
                    cand = self._select_biased_candidate(s_allowed, u, w, g_s, needed_dist / 2.0)
                    new_wps[s_idx].insert(ins_pos, cand)

        # -------------------------------------------------------------
        # k = 3: Ruin and Recreate (Reset etapu do cięciwy i świeży punkt)
        # -------------------------------------------------------------
        elif k == 3:
            new_wps[stage_idx] = [start_cp, dest_cp]
            clean_allowed = [n for n in allowed_candidates if n not in (start_cp, dest_cp)]
            if current_dist < self.params.target_distance and clean_allowed:
                fresh_cand = self._select_biased_candidate(clean_allowed, start_cp, dest_cp, graph, needed_dist)
                new_wps[stage_idx].insert(1, fresh_cand)

        # -------------------------------------------------------------
        # k = 4: Checkpoint Shift / Retract (Korekta węzła głównego checkpointu)
        # -------------------------------------------------------------
        elif k == 4:
            if self.num_stages > 1:
                cp_idx_to_shift = random.randint(1, self.num_stages - 1)
                curr_cp_node = self.checkpoints[cp_idx_to_shift]
                g_curr = self.stage_graphs[cp_idx_to_shift]

                c_cp = self._get_coord(curr_cp_node, g_curr)
                other_cps = {self.checkpoints[i] for i in range(self.num_stages) if i != cp_idx_to_shift}
                local_candidates = [
                    n
                    for n in self._stage_nodes_cache[cp_idx_to_shift]
                    if 30.0 <= haversine(self._get_coord(n, g_curr), c_cp) <= self.params.checkpoint_shift_radius_meters
                    and n not in other_cps
                ]

                if local_candidates:
                    replacement_cp = random.choice(local_candidates)
                    self.checkpoints[cp_idx_to_shift] = replacement_cp

                    prev_stage = (cp_idx_to_shift - 1) % self.num_stages
                    new_wps[prev_stage][-1] = replacement_cp
                    new_wps[cp_idx_to_shift][0] = replacement_cp

        return new_wps

    # --- WYGŁADZANIE TRASY (POST-PROCESSING: SPUR REMOVAL) ---

    def _smooth_route(self, full_path: list[int]) -> tuple[list[int], float]:
        """Usuwa lokalne mikro-wypustki bez ryzyka zwinięcia całej pętli ze startu do mety."""
        if not full_path or len(full_path) < 10:
            return full_path, self._calculate_path_distance(full_path)

        ref_graph = getattr(self.evaluator, "graph", self.stage_graphs[0])
        smoothed: list[int] = []
        i = 0
        n = len(full_path)
        original_dist = self._calculate_path_distance(full_path)

        while i < n:
            smoothed.append(full_path[i])
            curr_coord = self._get_coord(full_path[i], ref_graph)

            shortcut_found = False
            # Ograniczenie lookahead do max 8 węzłów (tylko mikro-zaułki)
            # ZABEZPIECZENIE: j nie może sięgać do samego końca trasy (omijamy metę pętli)
            max_lookahead = min(i + 8, n - 2) if i < 5 else min(i + 8, n - 1)

            for j in range(max_lookahead, i + 3, -1):
                # Jeśli sprawdzamy węzły blisko początku i końca pętli, pomijamy (to nie jest odnoga, to domknięcie)
                if i < 3 and j > n - 5:
                    continue

                target_coord = self._get_coord(full_path[j], ref_graph)

                # Tylko bardzo ciasne, ewidentne zawrotki w promieniu 20m
                if haversine(curr_coord, target_coord) < 20.0:
                    try:
                        shortcut = nx.shortest_path(
                            ref_graph, source=full_path[i], target=full_path[j], weight="length"
                        )
                        if len(shortcut) < (j - i):
                            smoothed.extend(shortcut[1:])
                            i = j
                            shortcut_found = True
                            break
                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        continue

            if not shortcut_found:
                i += 1

        smoothed_dist = self._calculate_path_distance(smoothed)

        # ZABEZPIECZENIE ANTY-KASACYJNE:
        # Jeśli wygładzanie zjadło trasę (np. na wsi, gdzie powrót szosą był celowy),
        # bezwzględnie porzucamy skróty i zachowujemy oryginalną trasę VNS.
        if smoothed_dist < 0.6 * self.params.target_distance or len(smoothed) < 4:
            return full_path, original_dist

        return smoothed, smoothed_dist

    def _calculate_path_distance(self, path: list[int]) -> float:
        """Szybkie sumowanie odległości ścieżki z cache krawędzi."""
        if not path or len(path) < 2:
            return 0.0
        return sum(
            self.evaluator.edge_info_cache.get((u, v), ([], 1.0))[1] for u, v in zip(path[:-1], path[1:], strict=False)
        )

    def _log_operator_stats(self) -> None:
        """Wypisuje zestawienie skuteczności operatorów sąsiedztwa."""
        print("\n" + "=" * 68)
        print("📊 PODSUMOWANIE SKUTECZNOŚCI STRUKTUR SĄSIEDZTWA (VNS)")
        print("=" * 68)
        print(f"{'k':<3} | {'Nazwa operatora':<30} | {'Wywołania':<10} | {'Sukcesy':<8} | {'Hit Rate':<8}")
        print("-" * 68)

        for k in range(1, self.params.max_k + 1):
            name = self.OPERATOR_NAMES.get(k, f"Neighborhood {k}")
            calls = self.operator_stats[k]["calls"]
            imp = self.operator_stats[k]["improvements"]
            hit_rate = (imp / calls * 100.0) if calls > 0 else 0.0
            print(f"{k:<3} | {name:<30} | {calls:<10} | {imp:<8} | {hit_rate:>6.1f}%")

        print("=" * 68 + "\n")

    # --- PĘTLA GŁÓWNA OPTYMALIZACJI ---

    def generate_route(self) -> tuple[list[int], float]:
        """Uruchamia optymalizację VNS z próbną inicjalizacją, adaptacyjną selekcją sąsiedztw
        oraz końcowym wygładzaniem trasy z niepotrzebnych odnóg.
        """
        # 1. Inicjalizacja szkieletu bazowego
        current_stage_wps: list[list[int]] = []
        for i in range(self.num_stages):
            start_cp = self.checkpoints[i]
            dest_cp = self.checkpoints[(i + 1) % self.num_stages]
            current_stage_wps.append([start_cp, dest_cp])

        best_path, best_dist, best_fitness = self._evaluate_candidate_stages(current_stage_wps)

        # 2. Próbkowanie początkowych detours (Initial Sampling)
        for _ in range(self.params.num_initial_samples - 1):
            sample_wps = [list(stage) for stage in current_stage_wps]
            for s_idx in range(self.num_stages):
                s_nodes = self._stage_nodes_cache[s_idx]
                g_s = self.stage_graphs[s_idx]
                s_existing = set(sample_wps[s_idx])
                s_allowed = [
                    n
                    for n in s_nodes
                    if not self._is_in_terminal_zone(n, sample_wps[s_idx][0], sample_wps[s_idx][-1], g_s)
                    and n not in s_existing
                ]
                if s_allowed:
                    cand = self._select_biased_candidate(
                        s_allowed,
                        sample_wps[s_idx][0],
                        sample_wps[s_idx][-1],
                        g_s,
                        (self.params.target_distance - best_dist) / self.num_stages,
                    )
                    sample_wps[s_idx].insert(1, cand)

            s_path, s_dist, s_fitness = self._evaluate_candidate_stages(sample_wps)
            if s_path and s_fitness > best_fitness:
                best_fitness = s_fitness
                best_path = s_path
                best_dist = s_dist
                current_stage_wps = [list(s) for s in sample_wps]

        # Jeśli po wszystkich próbach fallback nie spiął szkieletu bazowego:
        if not best_path:
            return [], -1.0

        current_dist = best_dist
        best_wps = [list(s) for s in current_stage_wps]

        # 3. Główna pętla VNS
        k = 1
        iteration = 0
        stagnation_counter = 0

        while iteration < self.params.max_iterations:
            iteration += 1

            # 1. Warunek natychmiastowego sukcesu
            if best_fitness >= self.params.target_fitness:
                logger.info(f"🎯 Osiągnięto target fitness ({best_fitness:.4f}) w {iteration}. iteracji. Przerywam.")
                break

            cand_wps = self._shake(current_stage_wps, k, current_dist)
            cand_path, cand_dist, cand_fitness = self._evaluate_candidate_stages(cand_wps)

            if not cand_path:
                k = (k % self.params.max_k) + 1
                stagnation_counter += 1
                if stagnation_counter >= self.params.max_stagnation_iterations:
                    break
                continue

            # 2. Neighborhood Change (Akceptacja)
            if cand_fitness > best_fitness:
                self.operator_stats[k]["improvements"] += 1
                best_fitness = cand_fitness
                best_path = cand_path
                best_dist = cand_dist
                best_wps = [list(s) for s in cand_wps]

                current_stage_wps = [list(s) for s in cand_wps]
                current_dist = cand_dist

                k = 1
                stagnation_counter = 0  # Reset licznika stagnacji przy każdym sukcesie!
            else:
                k = (k % self.params.max_k) + 1
                stagnation_counter += 1

            # 3. Warunek zatrzymania z powodu braku poprawy
            if stagnation_counter >= self.params.max_stagnation_iterations:
                logger.info(f"🛑 Stagnacja ({stagnation_counter} iteracji bez poprawy). Kończę VNS.")
                break

        self._log_operator_stats()

        # 4. Post-processing: Wygładzanie trasy i usunięcie ślepych odnóg
        if best_path:
            best_path, best_dist = self._smooth_route(best_path)
            best_fitness = self.evaluator.evaluate(best_path, total_distance=best_dist)

            breakdown: EvaluationBreakdown = self.evaluator.evaluate_with_breakdown(best_path, best_dist)
            breakdown.log_summary("Best Found VNS Loop (Smoothed)")

        return best_path, best_fitness
