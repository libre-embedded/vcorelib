"""
A module exposing data-file encoders and decoders.
"""

# built-in
from io import StringIO
import logging
from pathlib import Path
from typing import Optional as _Optional

# third-party
import aiofiles

# internal
from vcorelib import DEFAULT_ENCODING as _DEFAULT_ENCODING
from vcorelib.dict import MergeStrategy, consume
from vcorelib.io.mapping import DataMapping
from vcorelib.io.types import DataDecoder as _DataDecoder
from vcorelib.io.types import DataEncoder as _DataEncoder
from vcorelib.io.types import DataStream as _DataStream
from vcorelib.io.types import EncodeResult as _EncodeResult
from vcorelib.io.types import JsonObject as _JsonObject
from vcorelib.io.types import LoadResult
from vcorelib.io.types import StreamProcessor as _StreamProcessor
from vcorelib.logging import LoggerType
from vcorelib.paths import Pathlike as _Pathlike
from vcorelib.paths import find_file, get_file_ext, normalize


class DataArbiterBase:
    """
    A class for looking up encode and decode functions for given data types.
    """

    def __init__(
        self,
        logger: LoggerType = logging.getLogger(__name__),
        encoding: str = _DEFAULT_ENCODING,
    ) -> None:
        """Initialize a new data arbiter."""
        self.logger = logger
        self.encoding = encoding

    def _decoder(self, ext: str) -> _Optional[_DataDecoder]:
        """Look up a decoding routine from a file extension."""

        result = None
        dtype = DataMapping.from_ext_str(ext)
        if dtype is not None:
            result = dtype.value.decoder
        else:
            self.logger.warning("No decoder for '%s'.", ext)
        return result

    def decode_stream(
        self,
        ext: str,
        stream: _DataStream,
        logger: LoggerType = None,
        **kwargs,
    ) -> LoadResult:
        """Attempt to load data from a text stream."""

        if logger is None:
            logger = self.logger

        result = LoadResult({}, False)
        decoder = self._decoder(ext)
        if decoder is not None:
            result = decoder(stream, logger, **kwargs)
        return result

    def _decode_stream(
        self,
        stream: _DataStream,
        ext: str,
        logger: LoggerType,
        preprocessor: _StreamProcessor = None,
        **kwargs,
    ) -> LoadResult:
        """A wrapper for stream decoding."""

        return self.decode_stream(
            ext,
            # Preprocess the stream if specified. This can be useful for
            # external code to treat data files as templates.
            (preprocessor(stream) if preprocessor is not None else stream),
            logger,
            **kwargs,
        )

    def _decode_file(
        self,
        path: Path,
        logger: LoggerType,
        preprocessor: _StreamProcessor = None,
        maxsplit: int = 1,
        **kwargs,
    ) -> LoadResult:
        """Decode a file via path."""

        with path.open(encoding=self.encoding) as path_fd:
            result = self._decode_stream(
                path_fd,
                get_file_ext(path, maxsplit=maxsplit),
                logger,
                preprocessor=preprocessor,
                **kwargs,
            )

        return result

    async def _decode_file_async(
        self,
        path: Path,
        logger: LoggerType,
        preprocessor: _StreamProcessor = None,
        maxsplit: int = 1,
        **kwargs,
    ) -> LoadResult:
        """Decode a file via path using asyncio."""

        async with aiofiles.open(path, encoding=self.encoding) as path_fd:
            with StringIO(await path_fd.read()) as stream:
                result = self._decode_stream(
                    stream,
                    get_file_ext(path, maxsplit=maxsplit),
                    logger,
                    preprocessor=preprocessor,
                    **kwargs,
                )

        return result

    async def decode_async(
        self,
        pathlike: _Pathlike,
        logger: LoggerType = None,
        require_success: bool = False,
        includes_key: str = None,
        preprocessor: _StreamProcessor = None,
        maxsplit: int = 1,
        expect_overwrite: bool = False,
        strategy: MergeStrategy = MergeStrategy.RECURSIVE,
        files_loaded: list[Path] = None,
        **kwargs,
    ) -> LoadResult:
        """Attempt to load data from a file using asyncio."""

        result = LoadResult({}, False)
        if logger is None:
            logger = self.logger

        # Keep track of all files that get loaded.
        if files_loaded is None:
            files_loaded = []

        path = normalize(pathlike)
        if path.is_file():
            result = await self._decode_file_async(
                path,
                logger,
                preprocessor=preprocessor,
                maxsplit=maxsplit,
                **kwargs,
            )

            if result:
                files_loaded.append(path)

            # Resolve includes if necessary.
            if includes_key is not None:
                for include in consume(result.data, includes_key, []):
                    # Load the included file.
                    result = result.merge(
                        await self.decode_async(
                            find_file(
                                include,
                                relative_to=path,
                                include_cwd=True,
                                strict=True,
                            ),
                            logger,
                            require_success=require_success,
                            includes_key=includes_key,
                            files_loaded=files_loaded,
                            **kwargs,
                        ),
                        expect_overwrite=expect_overwrite,
                        logger=logger,
                        strategy=strategy,
                    )
                    if result:
                        files_loaded.append(include)

                for include in consume(
                    result.data, f"{includes_key}_left", []
                ):
                    # Load the included file.
                    result = result.merge(
                        await self.decode_async(
                            find_file(
                                include,
                                relative_to=path,
                                include_cwd=True,
                                strict=True,
                            ),
                            logger,
                            require_success=require_success,
                            includes_key=includes_key,
                            files_loaded=files_loaded,
                            **kwargs,
                        ),
                        is_left=True,
                        expect_overwrite=expect_overwrite,
                        logger=logger,
                        strategy=strategy,
                    )
                    if result:
                        files_loaded.append(include)

        if not result.success:
            logger.error("Failed to decode '%s'.", path)

        # Raise an exception if we expected decoding to succeed.
        if require_success:
            result.require_success(path)

        return result

    def decode(
        self,
        pathlike: _Pathlike,
        logger: LoggerType = None,
        require_success: bool = False,
        includes_key: str = None,
        preprocessor: _StreamProcessor = None,
        maxsplit: int = 1,
        expect_overwrite: bool = False,
        strategy: MergeStrategy = MergeStrategy.RECURSIVE,
        files_loaded: list[Path] = None,
        **kwargs,
    ) -> LoadResult:
        """Attempt to load data from a file."""

        result = LoadResult({}, False)
        if logger is None:
            logger = self.logger

        # Keep track of all files that get loaded.
        if files_loaded is None:
            files_loaded = []

        path = normalize(pathlike)
        if path.is_file():
            result = self._decode_file(
                path,
                logger,
                preprocessor=preprocessor,
                maxsplit=maxsplit,
                **kwargs,
            )

            if result:
                files_loaded.append(path)

            # Resolve includes if necessary.
            if includes_key is not None:
                for include in consume(result.data, includes_key, []):
                    # Load the included file.
                    result = result.merge(
                        self.decode(
                            find_file(
                                include,
                                relative_to=path,
                                include_cwd=True,
                                strict=True,
                            ),
                            logger,
                            require_success=require_success,
                            includes_key=includes_key,
                            files_loaded=files_loaded,
                            **kwargs,
                        ),
                        expect_overwrite=expect_overwrite,
                        logger=logger,
                        strategy=strategy,
                    )

                for include in consume(
                    result.data, f"{includes_key}_left", []
                ):
                    # Load the included file.
                    result = result.merge(
                        self.decode(
                            find_file(
                                include,
                                relative_to=path,
                                include_cwd=True,
                                strict=True,
                            ),
                            logger,
                            require_success=require_success,
                            includes_key=includes_key,
                            files_loaded=files_loaded,
                            **kwargs,
                        ),
                        is_left=True,
                        expect_overwrite=expect_overwrite,
                        logger=logger,
                        strategy=strategy,
                    )

        if not result.success:
            logger.error("Failed to decode '%s'.", path)

        # Raise an exception if we expected decoding to succeed.
        if require_success:
            result.require_success(path)

        return result

    def encode_stream(
        self,
        ext: str,
        stream: _DataStream,
        data: _JsonObject,
        logger: LoggerType = None,
        **kwargs,
    ) -> _EncodeResult:
        """Serialize data to an output stream."""

        if logger is None:
            logger = self.logger

        result = False
        encoder = self._encoder(ext)
        time_ns = -1
        if encoder is not None:
            time_ns = encoder(data, stream, logger, **kwargs)
            result = True
        return result, time_ns

    async def encode_async(
        self,
        pathlike: _Pathlike,
        data: _JsonObject,
        logger: LoggerType = None,
        maxsplit: int = 1,
        **kwargs,
    ) -> _EncodeResult:
        """Encode data to a file on disk using asyncio."""

        path = normalize(pathlike)
        async with aiofiles.open(
            path, mode="w", encoding=self.encoding
        ) as path_fd:
            with StringIO() as stream:
                result = self.encode_stream(
                    get_file_ext(path, maxsplit=maxsplit),
                    stream,
                    data,
                    logger,
                    **kwargs,
                )
                await path_fd.write(stream.getvalue())

        return result

    def encode(
        self,
        pathlike: _Pathlike,
        data: _JsonObject,
        logger: LoggerType = None,
        maxsplit: int = 1,
        **kwargs,
    ) -> _EncodeResult:
        """Encode data to a file on disk."""

        path = normalize(pathlike)
        with path.open("w", encoding=self.encoding) as path_fd:
            return self.encode_stream(
                get_file_ext(path, maxsplit=maxsplit),
                path_fd,
                data,
                logger,
                **kwargs,
            )

    def _encoder(self, ext: str) -> _Optional[_DataEncoder]:
        """Look up an encoding routine from a file extension."""

        result = None
        dtype = DataMapping.from_ext_str(ext)
        if dtype is not None:
            result = dtype.value.encoder
        else:
            self.logger.warning("No encoder for '%s'.", ext)
        return result
