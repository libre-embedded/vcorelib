"""
A module for defining and working with graph edges.
"""

# built-in
from typing import NamedTuple
from typing import Optional as _Optional
from typing import TextIO as _TextIO

# internal
from vcorelib.graph.port import Port as _Port

AttributeMap = dict[str, str]


def write_attributes(stream: _TextIO, data: AttributeMap = None) -> None:
    """A simple attribute writer for Graphviz's DOT language."""

    if data:
        stream.write(" [ ")
        attr_strs = [f'{k}="{v}"' for k, v in data.items()]
        stream.write(", ".join(attr_strs))
        stream.write(" ]")


def write_node_id(label: str, stream: _TextIO, port: _Port = None) -> None:
    """Write a node identifier to a stream."""

    stream.write(label)
    if port:
        stream.write(":")
        stream.write(port.label)


class GraphEdge(NamedTuple):
    """A grouping of attributes describing a directed edge in a graph."""

    src: str
    dst: str
    src_port: _Optional[_Port] = None
    dst_port: _Optional[_Port] = None
    attrs: _Optional[AttributeMap] = None

    def __eq__(self, other) -> bool:
        """Determine if this edge is equivalent to another."""
        return bool(self.src == other.src and self.dst == other.dst)

    def __hash__(self) -> int:
        """Use a string representation as a sane hashing method."""
        return hash(f"{self.src}:{self.dst}")

    def to_stream(self, stream: _TextIO, edgeop: str = "->", **_) -> None:
        """Write this object to a text stream."""

        write_node_id(self.src, stream, port=self.src_port)
        stream.write(f" {edgeop} ")
        write_node_id(self.dst, stream, port=self.dst_port)

        write_attributes(stream, data=self.attrs)
        stream.write(";")
