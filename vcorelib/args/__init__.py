"""
A module for working with application-specific argument parsers.
"""

# built-in
from argparse import ArgumentParser, Namespace
from typing import Callable as _Callable
from typing import Sequence as _Sequence

CommandFunction = _Callable[[Namespace], int]
CommandRegister = _Callable[[ArgumentParser], CommandFunction]

CommandLoader = _Callable[[], _Sequence[tuple[str, str, CommandRegister]]]

CMDS: dict[str, CommandFunction] = {}


def app_args(
    command_loader: CommandLoader, commands: dict[str, CommandFunction] = None
) -> tuple[_Callable[[ArgumentParser], None], CommandFunction]:
    """
    Create a function that can be used to add sub-command processing to an
    argument parser.
    """

    if commands is None:
        commands = CMDS

    def add_app_args(parser: ArgumentParser) -> None:
        """Add application-specific arguments to the command-line parser."""

        subparser = parser.add_subparsers(
            title="commands",
            dest="command",
            required=True,
            help="set of available commands",
        )
        assert commands is not None
        commands.update(
            {
                name: register(subparser.add_parser(name, help=cmd_help))
                for name, cmd_help, register in command_loader()
            }
        )

    def call_command(args: Namespace) -> int:
        """Call the specified command from parsed arguments."""
        assert commands is not None
        return commands[args.command](args)

    return add_app_args, call_command
