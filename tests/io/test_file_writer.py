"""
Test the 'io.file_writer' module.
"""

# built-in
from contextlib import ExitStack
from io import StringIO
from json import dumps
from os import linesep
from pathlib import Path
from tempfile import TemporaryDirectory

# module under test
from vcorelib.io.file_writer import CommentStyle, IndentedFileWriter


def lines(*parts: str) -> str:
    """Get a sequence of strings as lines."""
    return linesep.join(parts) + linesep


def test_file_writer_different():
    """Test write-if-different option for file writer."""

    with TemporaryDirectory() as tmpdir:
        out = Path(tmpdir, "out.txt")

        with IndentedFileWriter.from_path_if_different(out) as writer:
            writer.write("test123")

        with IndentedFileWriter.from_path_if_different(out) as writer:
            writer.write("test123")

        with IndentedFileWriter.from_path_if_different(out) as writer:
            writer.write("test1234")


def test_file_writer_markdown():
    """Test writing markdown to a file."""

    with ExitStack() as stack:
        stream = stack.enter_context(StringIO())
        writer = IndentedFileWriter(stream)

        def write_message() -> None:
            """Write a sample message to the document."""
            writer.write("<!-- comment -->")
            writer.write_markdown(
                "# what is up y'all\n\nThis is my documentation.",
                hook=lambda x: x,
            )
            writer.write("<!-- comment -->")

        write_message()
        for _ in range(5):
            stack.enter_context(writer.indented())
            write_message()

        assert stream.getvalue()
        # print(stream.getvalue())

    # assert False


def test_file_writer_comment_lines():
    """Test the file-writer's line comment alignment."""

    assert CommentStyle.C_DOXYGEN.wrap("test") == "/*!< test */"

    with StringIO() as stream:
        writer = IndentedFileWriter(stream)

        with writer.trailing_comment_lines() as pairs:
            pairs.append(("a", "a"))
            pairs.append(("ab", None))
            pairs.append(("abc", "c"))

        assert stream.getvalue() == lines(
            "a   /* a */",
            "ab",
            "abc /* c */",
        )

    with StringIO() as stream:
        writer = IndentedFileWriter(stream)

        with writer.trailing_comment_lines(
            style=CommentStyle.SCRIPT, min_pad=2
        ) as pairs:
            pairs.append(("a", "a"))
            pairs.append(("ab", None))
            pairs.append(("abc", "c"))

        assert stream.getvalue() == lines(
            "a    # a",
            "ab",
            "abc  # c",
        )


def test_file_writer_scope():
    """Test various programming-language scoping invocations."""

    with StringIO() as stream:
        writer = IndentedFileWriter(stream, per_indent=4)
        with writer.scope(prefix="struct MyStruct ", suffix=";"):
            writer.c_comment("A comment.")
            writer.c_comment("Another comment.")

            writer.empty(count=2)
            writer.write("")

            with writer.padding():
                writer.write(dumps({"a": 1, "b": 2, "c": 3}, indent=4))

            with writer.padding():
                pass

            writer.join("TEST")
            writer.join("A", "B", "C")

        assert stream.getvalue() == lines(
            "struct MyStruct {",
            "    /* A comment. */",
            "    /* Another comment. */",
            "",
            "",
            "",
            "",
            "    {",
            '        "a": 1,',
            '        "b": 2,',
            '        "c": 3',
            "    }",
            "",
            "",
            "    TEST",
            "    A,",
            "    B,",
            "    C",
            "};",
        )

    with StringIO() as stream:
        writer = IndentedFileWriter(stream, per_indent=4)
        with writer.indented():
            with writer.javadoc():
                writer.write("A comment.")
                writer.write("Another comment.")

                writer.write("")
                writer.write(dumps({"a": 1, "b": 2, "c": 3}, indent=4))
                writer.empty(count=2)

            with writer.scope():
                writer.cpp_comment("Yup.")

        print(stream.getvalue())

        assert stream.getvalue() == lines(
            "    /**",
            "     * A comment.",
            "     * Another comment.",
            "     *",
            "     * {",
            '     *     "a": 1,',
            '     *     "b": 2,',
            '     *     "c": 3',
            "     * }",
            "     *",
            "     *",
            "     */",
            "    {",
            "        // Yup.",
            "    }",
        )


def test_file_writer_basic():
    """Test basic interactions with the indented file-writer."""

    with IndentedFileWriter.temporary() as writer:
        writer.write("Hello, world!")

    with IndentedFileWriter.string() as writer:
        writer.write("Hello, world!")

    with StringIO() as stream:
        writer = IndentedFileWriter(stream)
        writer.write("Hello, world!")

        # Check output.
        assert stream.getvalue() == "Hello, world!" + linesep

    with StringIO() as stream:
        writer = IndentedFileWriter(stream)
        writer.indent()
        writer.write("Hello, world!")

        # Check output.
        assert stream.getvalue() == " Hello, world!" + linesep

    with StringIO() as stream:
        writer = IndentedFileWriter(stream, per_indent=4)
        writer.dedent()

        with writer.indented():
            writer.write("Hello, world!")

        # Check output.
        assert stream.getvalue() == "    Hello, world!" + linesep

        writer.write("Hello, world!")

        assert (
            stream.getvalue()
            == "    Hello, world!" + linesep + "Hello, world!" + linesep
        )
