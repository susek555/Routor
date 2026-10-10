import networkx as nx

from src.generate_routes.data.map import Map

EXPECTED_CHECKPOINT_COUNT = 4


class CheckpointRefiner:
    @staticmethod
    def _get_edge_length(graph: Map, u: int, v: int) -> float:
        """Safely fetches edge length regardless of direction or multigraph structure."""
        data = graph.get_edge_data(u, v) or graph.get_edge_data(v, u) or {}
        if "length" in data:
            return float(data["length"])
        if isinstance(data, dict) and data:
            lengths = [d.get("length", 0.0) for d in data.values() if isinstance(d, dict)]
            if lengths:
                return float(min(lengths))
        return 0.0

    @classmethod
    def _evaluate_checkpoint_spur(
        cls,
        graph_in: Map,
        graph_out: Map,
        nodes: tuple[int, int, int],
        max_retraction_meters: float,
        checkpoint_idx: int,
    ) -> int | None:
        """Detects if curr_node is an out-and-back spur between adjacent stage subgraphs.

        Returns the fork node if the spur is within budget, otherwise None.
        """
        prev_node, curr_node, next_node = nodes

        if not graph_in.has_node(curr_node) or not graph_out.has_node(curr_node):
            print(f"   [CP{checkpoint_idx}] ⚠️ Missing node {curr_node} at subgraph junction")
            return None

        try:
            path_in = nx.shortest_path(graph_in, source=prev_node, target=curr_node, weight="length")
            path_out = nx.shortest_path(graph_out, source=curr_node, target=next_node, weight="length")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            print(f"   [CP{checkpoint_idx}] ⚠️ No valid path through adjacent stages")
            return None

        rev_in = list(reversed(path_in))
        max_check = min(len(rev_in), len(path_out))
        overlap_count = 0

        while overlap_count < max_check and rev_in[overlap_count] == path_out[overlap_count]:
            overlap_count += 1

        if overlap_count <= 1:
            print(f"   [CP{checkpoint_idx}] ℹ️ No overlapping edges (smooth transit)")
            return None

        spur_nodes = rev_in[:overlap_count]
        fork_candidate = spur_nodes[-1]

        spur_len = sum(
            cls._get_edge_length(graph_in, u, v) for u, v in zip(spur_nodes[:-1], spur_nodes[1:], strict=False)
        )
        total_spur_cost = spur_len * 2.0

        print(f"   [CP{checkpoint_idx}] 🔍 Detected spur: {spur_len:.1f}m (round-trip: {total_spur_cost:.1f}m)")

        if total_spur_cost <= max_retraction_meters:
            print(f"   [CP{checkpoint_idx}] ✂️ Collapsing checkpoint to fork: node {fork_candidate}")
            return fork_candidate

        print(
            f"   [CP{checkpoint_idx}] ⛔ Spur too long "
            f"({total_spur_cost:.1f}m > limit {max_retraction_meters:.1f}m) - preserving out-and-back"
        )
        return None

    @classmethod
    def refine_stage_checkpoints(
        cls,
        stage_subgraphs: list[Map],
        checkpoint_node_ids: list[int],
        target_distance_meters: float,
        max_retraction_ratio: float = 0.15,
    ) -> tuple[list[int], list[Map]]:
        """Refines all intermediate transit checkpoints by collapsing spurs into forks across adjacent stages."""
        if len(checkpoint_node_ids) != EXPECTED_CHECKPOINT_COUNT or len(stage_subgraphs) != EXPECTED_CHECKPOINT_COUNT:
            return list(checkpoint_node_ids), stage_subgraphs

        closed_ids = list(checkpoint_node_ids) + [checkpoint_node_ids[0]]
        max_retraction_meters = target_distance_meters * max_retraction_ratio

        # Iterate through intermediate checkpoints: CP1, CP2, CP3
        for i in range(1, EXPECTED_CHECKPOINT_COUNT):
            graph_in = stage_subgraphs[i - 1]
            graph_out = stage_subgraphs[i]
            nodes_triplet = (closed_ids[i - 1], closed_ids[i], closed_ids[i + 1])

            fork_node = cls._evaluate_checkpoint_spur(
                graph_in=graph_in,
                graph_out=graph_out,
                nodes=nodes_triplet,
                max_retraction_meters=max_retraction_meters,
                checkpoint_idx=i,
            )

            if fork_node is not None:
                closed_ids[i] = fork_node
                if not graph_in.has_node(fork_node):
                    graph_in.add_node(fork_node)
                if not graph_out.has_node(fork_node):
                    graph_out.add_node(fork_node)

        return closed_ids[:EXPECTED_CHECKPOINT_COUNT], stage_subgraphs
