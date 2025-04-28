"""
A task definition for melding inbox data into outbox data.
"""

# built-in
from typing import Any as _Any

# internal
from vcorelib.dict import merge, merge_dicts
from vcorelib.task import Inbox as _Inbox
from vcorelib.task import Outbox, Task


class DictMerger(Task):
    """A class that pipes inbox data through to outbox data."""

    async def run(
        self, inbox: _Inbox, outbox: Outbox, *args, **kwargs
    ) -> bool:
        """Override this method to implement the task."""

        # Forward the foreign argument to the ouput box (provided by the
        # caller).
        to_merge: list[dict[_Any, _Any]] = [outbox]
        for arg in [*args]:
            if isinstance(arg, dict):
                to_merge.append(arg)
        to_merge.append(kwargs)

        expect_overwrite = kwargs.pop("expect_overwrite", False)
        merge_dicts(
            to_merge, expect_overwrite=expect_overwrite, logger=self.log
        )

        # Forward all inputs to the output box.
        merge(
            outbox, inbox, expect_overwrite=expect_overwrite, logger=self.log
        )
        return True
