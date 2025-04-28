"""
A module for working with graph ports.
"""

from enum import Enum as _Enum
from enum import auto as _auto

# built-in
from itertools import zip_longest as _zip_longest
from typing import NamedTuple
from typing import Optional as _Optional
from typing import TextIO as _TextIO


class PortType(_Enum):
    """An enumeration of port types."""

    INPUT = _auto()
    OUTPUT = _auto()
    INOUT = _auto()

    def __str__(self) -> str:
        """Get this port type as a string."""
        return self.name.lower()

    @property
    def is_input(self) -> bool:
        """Determine if this port type is capable of input."""
        return self is not PortType.OUTPUT

    @property
    def is_output(self) -> bool:
        """Determine if this port type is capable of output."""
        return self is not PortType.INPUT


class Port(NamedTuple):
    """A simple implementation for generic, input and output ports."""

    label: str
    kind: PortType = PortType.INOUT
    alias: _Optional[str] = None
    allocated: bool = False

    def allocate(self) -> "Port":
        """Allocate this port."""

        assert not self.allocated, f"Port '{self}' is already allocated!"
        return Port(
            self.label, kind=self.kind, alias=self.alias, allocated=True
        )

    def __str__(self) -> str:
        """Get this port as a string."""

        result = self.label
        alloc_str = "x" if self.allocated else " "
        result = f"{self.label}[{self.kind}][{alloc_str}]"
        if self.alias:
            result += f" ({self.alias})"
        return result

    @property
    def is_input(self) -> bool:
        """Determine if this is an input port."""
        return self.kind.is_input

    @property
    def is_output(self) -> bool:
        """Determine if this is an output port."""
        return self.kind.is_output


class PortManager:
    """An interface for managing input and output ports."""

    def __init__(self) -> None:
        """Initialize this port manager."""

        self.outputs: dict[str, Port] = {}
        self.inputs: dict[str, Port] = {}

    def inout_labels(self) -> set[str]:
        """Get inout port labels."""
        return set(self.inputs.keys()).intersection(self.outputs.keys())

    def input_labels(self, exclude_inout: bool = True) -> set[str]:
        """Get input port labels."""

        result = set(self.inputs.keys())
        if exclude_inout:
            result -= self.inout_labels()
        return result

    def output_labels(self, exclude_inout: bool = True) -> set[str]:
        """Get output port labels."""

        result = set(self.outputs.keys())
        if exclude_inout:
            result -= self.inout_labels()
        return result

    def label(self, stream: _TextIO) -> None:
        """Create a record label based on the current port configuration."""

        columns = []

        # Handle inout ports.
        inouts = "|".join(
            [f"<{x}> {self.outputs[x]}" for x in sorted(self.inout_labels())]
        )
        columns.append(inouts if inouts else "no inout ports")

        # Put inputs above outputs and arrange in a table.
        for in_label, out_label in _zip_longest(
            sorted(self.input_labels()), sorted(self.output_labels())
        ):
            in_data = (
                f"<{in_label}> {self.inputs[in_label]}" if in_label else ""
            )
            out_data = (
                f"<{out_label}> {self.outputs[out_label]}" if out_label else ""
            )
            columns.append("{" + in_data + "|" + out_data + "}")

        # Write columns to the stream.
        stream.write("|".join(columns))

    def create(self, label: str, **kwargs) -> Port:
        """Add a new port to this port manager."""

        port = Port(label, **kwargs)

        # Ensure the port's alias doesn't alias an existing input or output
        # port.
        if port.alias:
            assert (
                port.alias not in self.inputs
            ), f"Port alias '{port.alias}' is already an input label!"
            assert (
                port.alias not in self.outputs
            ), f"Port alias '{port.alias}' is already an output label!"

        if port.is_input:
            assert label not in self.inputs, f"Duplicate input port '{port}'!"
            self.inputs[label] = port

        if port.is_output:
            assert (
                label not in self.outputs
            ), f"Duplicate output port '{port}'!"
            self.outputs[label] = port

        return port

    def allocate(self, label: str) -> Port:
        """Allocate a labeled port."""

        port = None

        if label in self.inputs:
            port = self.inputs[label].allocate()
            self.inputs[label] = port

        if label in self.outputs:
            # Don't create a new port if it's an inout.
            if port is None:
                port = self.outputs[label].allocate()
            self.outputs[label] = port

        assert port is not None, f"Port '{label}' not found!"
        return port
