import numpy as np

from src.generate_routes.data.map import Map


class EdgePheromoneRegistry:
    """Manages a compact 1D pheromone array for sparse urban graphs."""

    def __init__(self, stage_graphs: list[Map], initial_pheromone: float = 1.0):
        self.initial_pheromone = float(initial_pheromone)
        self.edge_to_id: dict[frozenset[int], int] = {}
        self.id_to_edge: list[frozenset[int]] = []

        # Collect unique undirected edges across all stage subgraphs
        for graph in stage_graphs:
            for u, v in graph.edges():
                key = frozenset((u, v))
                if key not in self.edge_to_id:
                    idx = len(self.id_to_edge)
                    self.edge_to_id[key] = idx
                    self.id_to_edge.append(key)

        # 1D pheromone array of length M
        self.pheromones: np.ndarray = np.full(len(self.id_to_edge), self.initial_pheromone, dtype=np.float32)

    def get_edge_id(self, u: int | frozenset[int], v: int | None = None) -> int | None:
        """Returns the flat index for undirected edge {u, v} or frozenset. Returns None if invalid."""
        if isinstance(u, frozenset):
            key = u
        elif v is not None:
            key = frozenset((u, v))
        else:
            return None


        # Ignore self-loops (u == v)
        EDGE_LEN = 2
        if len(key) < EDGE_LEN:
            return None

        return self.edge_to_id.get(key)

    def get_pheromone(self, u: int, v: int) -> float:
        """Retrieves the current pheromone level for edge {u, v}."""
        idx = self.edge_to_id[frozenset((u, v))]
        return float(self.pheromones[idx])

    def evaporate(self, evaporation_rate: float) -> None:
        """Vectorized pheromone evaporation: tau <- tau * (1.0 - rho)."""
        self.pheromones *= 1.0 - evaporation_rate

    def apply_deposits(self, deposits: np.ndarray, min_tau: float = 1e-4, max_tau: float = 100.0) -> None:
        """Adds accumulated deposits and clamps pheromones within bounds."""
        self.pheromones += deposits
        np.clip(self.pheromones, min_tau, max_tau, out=self.pheromones)

    def create_empty_deposit_buffer(self) -> np.ndarray:
        """Creates a zero-initialized buffer for deposits accumulated during one iteration."""
        return np.zeros_like(self.pheromones)
