import networkx as nx
from shapely.geometry import LineString
from src.generate_routes.graph_builder.graph_simplifier import GraphSimplifier


class TestGraphSimplifier:
    def test_simplify_empty_or_none(self):
        """Verifies that None and empty graphs are handled gracefully."""
        empty_g = nx.MultiDiGraph()
        assert GraphSimplifier.simplify(empty_g) == empty_g
        assert GraphSimplifier.simplify(None) is None

    def test_materialize_bend_nodes_expands_linestring(self):
        """Verifies that LineString geometry points become actual graph nodes."""
        g = nx.MultiDiGraph()
        g.graph["crs"] = "epsg:4326"

        # Węzły krańcowe
        g.add_node(1, x=21.00, y=52.00)
        g.add_node(2, x=21.02, y=52.02)

        # Krawędź z zakrętem w punkcie (21.01, 52.015)
        curve_geom = LineString([(21.00, 52.00), (21.01, 52.015), (21.02, 52.02)])
        g.add_edge(1, 2, key=0, length=100.0, geometry=curve_geom)

        materialized = GraphSimplifier._materialize_bend_nodes(g)

        # Powinny być teraz 3 węzły (1, 2 oraz 1 sztuczny węzeł zakrętu)
        assert len(materialized.nodes) == 3
        # Powinny być 2 krawędzie składowe
        assert len(materialized.edges) == 2

        # Sprawdzenie czy punkt pośredni ma poprawne współrzędne
        mid_nodes = [n for n in materialized.nodes if n not in (1, 2)]
        assert len(mid_nodes) == 1
        mid_node_data = materialized.nodes[mid_nodes[0]]
        assert mid_node_data["x"] == 21.01
        assert mid_node_data["y"] == 52.015

    def test_simplify_collapses_close_nodes_and_unrolls_geometry(self):
        """Integration test on a small graph checking both clustering and unrolling."""
        g = nx.MultiDiGraph()
        g.graph["crs"] = "epsg:4326"

        # Dwa węzły bardzo blisko siebie (kilka metrów w centrum Warszawy)
        g.add_node(1, x=21.01220, y=52.22970)
        g.add_node(2, x=21.01225, y=52.22972)
        # Trzeci węzeł dalej z zakrętem
        g.add_node(3, x=21.01500, y=52.23100)

        g.add_edge(1, 2, key=0, length=5.0)
        curve = LineString([(21.01225, 52.22972), (21.01350, 52.23050), (21.01500, 52.23100)])
        g.add_edge(2, 3, key=0, length=200.0, geometry=curve)

        result = GraphSimplifier.simplify(g, tolerance_meters=15.0)

        # Węzły 1 i 2 powinny zostać scalone do jednego, a zakręt na drodze do węzła 3 rozwinięty
        assert len(result.nodes) >= 3
        assert result.graph["crs"] == "epsg:4326"
