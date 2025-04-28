"""
A module containing abstract base-classes related to graphs.
"""

# built-in
from collections import UserDict as _UserDict
from typing import Iterator as _Iterator
from typing import Type as _Type
from typing import TypeVar as _TypeVar

# internal
from vcorelib.graph.edge import AttributeMap as _AttributeMap
from vcorelib.graph.edge import GraphEdge as _GraphEdge
from vcorelib.graph.port import Port as _Port
from vcorelib.graph.port import PortManager as _PortManager
from vcorelib.io.abc import Serializable as _Serializable

T = _TypeVar("T", bound="AbstractDiGraphNode")
V = _TypeVar("V", bound="AbstractDiGraph")


class AbstractDiGraphNode(_Serializable):
    """A base interface for a directed-graph node."""

    def __init__(
        self, graph: V = None, label: str = None, port: _Port = None, **attrs
    ) -> None:
        """Initialize this graph node."""

        self._graph = graph
        self._label = label
        self.port = port
        self.node_attributes = {**attrs}
        self.ports = _PortManager()

    def add_port(self, label: str, **kwargs) -> _Port:
        """Add a port to this graph node."""
        return self.ports.create(label, **kwargs)

    def allocate_port(self, label: str) -> _Port:
        """Allocate a port on this node."""
        return self.ports.allocate(label)

    def graph(self, kind: _Type[V] = None) -> V:
        """Get the graph that this node belongs to."""
        del kind
        assert self._graph is not None, "Node hasn't joined a graph!"
        return self._graph  # type: ignore

    @property
    def label(self) -> str:
        """Get this node's label."""
        assert self._label is not None, "Node hasn't joined a graph!"
        return self._label

    def join_graph(self, graph: V, label: str) -> None:
        """Attempt to join a graph."""

        # Verify the graph assignment.
        assert (
            self._graph is None or self._graph is graph
        ), f"Node '{self}' is already part of a different graph!"

        # Verify the label assignment.
        assert (
            self._label is None or self._label == label
        ), f"Node already has label '{self._label}' (!= '{label}')!"

        self._graph = graph  # type: ignore
        self._label = label

    def outgoing(self, graph_kind: _Type[V] = None) -> _Iterator[T]:
        """Iterate over nodes that we have outgoing edges to."""

        graph = self.graph(kind=graph_kind)

        for edge in graph.edges[self.label]:
            yield graph[edge.dst]

    def incoming(self, graph_kind: _Type[V] = None) -> _Iterator[T]:
        """Iterate over nodes that have incoming edges."""

        graph = self.graph(kind=graph_kind)

        for label, edges in graph.edges.items():
            for edge in edges:
                if self.label == edge.dst:
                    yield graph[label]
                    break

    def parallel(self) -> set[T]:
        """Iterate over nodes that this instance shares parallel edges with."""

        outgoing: set[T] = set(self.outgoing())
        incoming: set[T] = set(self.incoming())
        return outgoing.intersection(incoming)


class AbstractDiGraph(
    _UserDict,  # type: ignore
    _Serializable,
):
    """A simple, directed-graph interface."""

    def __init__(
        self,
        name: str,
        initialdata: dict[str, T] = None,
        graph_attrs: _AttributeMap = None,
        node_attrs: _AttributeMap = None,
        edge_attrs: _AttributeMap = None,
    ) -> None:
        """Initialize this graph."""

        self.name = name
        super().__init__(initialdata)
        self.graph_attrs = graph_attrs
        self.node_attrs = node_attrs
        self.edge_attrs = edge_attrs

        # Source node -> a set of all destination edges.
        self.edges: dict[str, set[_GraphEdge]] = {}

    def handle_node(self, label: str, node: T = None) -> T:
        """
        Handle either adding a node as a new vertex or obtaining an existing
        one.
        """

        if node is None:
            assert label in self.data, f"No node '{label}'!"
            node = self.data[label]
        else:
            node = self.add_vertex(label, node)

        return node

    def add_vertex(self, label: str, node: T) -> T:
        """Add a vertext to the graph."""

        assert (
            label not in self.data or self.data[label] is node
        ), f"Duplicate label '{label}'!"

        if label not in self.data:
            # Add a reference for the graph node to the graph itself.
            node.join_graph(self, label)

            # Add the node to the graph.
            self.data[label] = node
            self.edges[label] = set()

        return node

    def add_edge(
        self,
        src: str,
        dst: str,
        src_port: str = None,
        dst_port: str = None,
        strict: bool = False,
        **attrs,
    ) -> None:
        """Add an edge between nodes in the graph."""

        assert src in self.data, f"Source vertex '{src}' not in graph!"
        assert dst in self.data, f"Destination vertex '{dst}' not in graph!"

        # Allocate a source port if a label was provided.
        sport = None
        if src_port:
            sport = self.data[src].allocate_port(src_port)

            # Verify the source port is an output.
            assert (
                sport.is_output
            ), f"Source port '{sport}' ('{src}') is not an output!"

        # Allocate a destination port if a label was provided.
        dport = None
        if dst_port:
            dport = self.data[dst].allocate_port(dst_port)

            # Verify the destination port is an input.
            assert (
                dport.is_input
            ), f"Destination port '{dport}' ('{dst}') is not an input!"

        edge = _GraphEdge(
            src, dst, src_port=sport, dst_port=dport, attrs={**attrs}
        )
        edges = self.edges[src]

        # Prevent adding duplicate edges if desired.
        assert (
            not strict or edge not in edges
        ), f"Edge '{src}' -> '{dst}' already present!"

        edges.add(edge)

    def add_parallel(
        self,
        node1: str,
        node2: str,
        src_port1: str = None,
        dst_port1: str = None,
        src_port2: str = None,
        dst_port2: str = None,
        **kwargs,
    ) -> None:
        """Add an edge in each direction for two nodes."""

        self.add_edge(
            node1, node2, src_port=src_port1, dst_port=dst_port1, **kwargs
        )
        self.add_edge(
            node2, node1, src_port=src_port2, dst_port=dst_port2, **kwargs
        )

    def is_parallel(self, node1: str, node2: str) -> bool:
        """Determine if parallel edges exist between two nodes."""

        success = node1 in self.data and node2 in self.data

        if success:
            success = False

            # Check if we have a destination edge to node1 from node2.
            for edge in self.edges[node1]:
                if edge.dst == node2:
                    success = True
                    break

            if success:
                success = False

                # Check if we have a destination edge to node2 from node1.
                for edge in self.edges[node2]:
                    if edge.dst == node1:
                        success = True
                        break

        return success
