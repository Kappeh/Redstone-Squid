import re
from traceback import format_tb
from types import TracebackType
from typing import overload, Literal, Any

import discord
from discord import Message, Webhook
from discord.abc import Messageable

from bot.config import OWNER_ID, PRINT_TRACEBACKS
from database.database import DatabaseManager
from database.schema import RECORD_CATEGORIES, DOOR_ORIENTATION_NAMES

discord_red = 0xF04747
discord_yellow = 0xFAA61A
discord_green = 0x43B581


def error_embed(title: str, description: str | None):
    if description is None:
        description = ""
    return discord.Embed(title=title, colour=discord_red, description=":x: " + description)


def warning_embed(title: str, description: str | None):
    if description is None:
        description = ""
    return discord.Embed(title=":warning: " + title, colour=discord_yellow, description=description)


def info_embed(title: str, description: str | None):
    if description is None:
        description = ""
    return discord.Embed(title=title, colour=discord_green, description=description)


def help_embed(title: str, description: str | None):
    if description is None:
        description = ""
    return discord.Embed(title=title, colour=discord_green, description=description)


@overload
def parse_dimensions(dim_str: str) -> tuple[int, int, int | None]: ...


@overload
def parse_dimensions(
    dim_str: str, *, min_dim: int, max_dim: Literal[3]
) -> tuple[int, int | None, int | None]: ...


def parse_dimensions(dim_str: str, *, min_dim: int = 2, max_dim: int = 3) -> tuple[int | None, ...]:
    """Parses a string representing dimensions. For example, '5x5' or '5x5x5'. Both 'x' and '*' are valid separators.

    Args:
        dim_str: The string to parse
        min_dim: The minimum number of dimensions
        max_dim: The maximum number of dimensions

    Returns:
        A list of the dimensions, the length of the list will be padded with None to match `max_dim`.
    """
    if min_dim > max_dim:
        raise ValueError(f"min_dim must be less than or equal to max_dim. Got {min_dim=} and {max_dim=}.")

    inputs_cross = dim_str.split("x")
    inputs_star = dim_str.split("*")
    if min_dim <= len(inputs_cross) <= max_dim:
        inputs = inputs_cross
    elif min_dim <= len(inputs_star) <= max_dim:
        inputs = inputs_star
    else:
        raise ValueError(
            f"Invalid number of dimensions. Expected {min_dim} to {max_dim} dimensions, found {len(inputs_cross)} in {dim_str=} splitting by 'x', and {len(inputs_star)} splitting by '*'."
        )

    try:
        dimensions = list(map(int, inputs))
    except ValueError:
        raise ValueError(f"Invalid input. Each dimension must be parsable as an integer, found {inputs}")

    # Pad with None
    return tuple(dimensions + [None] * (max_dim - len(dimensions)))


def parse_hallway_dimensions(dim_str: str) -> tuple[int | None, int | None, int | None]:
    """Parses a string representing the door's <size>, which essentially is the hallway's dimensions.

    Examples:
        "5x5x5" -> (5, 5, 5)
        "5x5" -> (5, 5, None)
        "5 wide" -> (5, None, None)
        "5 high" -> (None, 5, None)

    References:
        https://docs.google.com/document/d/1kDNXIvQ8uAMU5qRFXIk6nLxbVliIjcMu1MjHjLJrRH4/edit

    Returns:
        A tuple of the dimensions (width, height, depth).
    """
    try:
        return parse_dimensions(dim_str)
    except ValueError:
        if match := re.match(r"^(\d+)\s*(wide|high)$", dim_str):
            size, direction = match.groups()
            if direction == "wide":
                return int(size), None, None
            else:  # direction == "high"
                return None, int(size), None
        else:
            raise ValueError(
                "Invalid hallway size. Must be in the format 'width x height [x depth]' or '<width> wide' or '<height> high'"
            )


class RunningMessage:
    """Context manager to show a working message while the bot is working."""

    def __init__(
        self,
        ctx: Messageable | Webhook,
        *,
        title: str = "Working",
        description: str = "Getting information...",
        delete_on_exit: bool = False,
    ):
        self.ctx = ctx
        self.title = title
        self.description = description
        self.delete_on_exit = delete_on_exit
        self.sent_message: Message

    async def __aenter__(self) -> Message:
        sent_message = await self.ctx.send(embed=info_embed(self.title, self.description))
        if sent_message is None:
            raise ValueError(
                "Failed to send message. (You are probably sending a message to a webhook, try looking into Webhook.send)"
            )

        self.sent_message = sent_message
        return sent_message

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> bool:
        # Handle exceptions
        if exc_type is not None:
            description = f"{str(exc_val)}"
            if PRINT_TRACEBACKS:
                description += f'\n\n```{"".join(format_tb(exc_tb))}```'
            await self.sent_message.edit(
                content=f"<@{OWNER_ID}>",
                embed=error_embed(f"An error has occurred: {exc_type.__name__}", description),
            )
            return False

        # Handle normal exit
        if self.delete_on_exit:
            await self.sent_message.delete()
        return False


async def parse_build_title(title: str) -> dict[str, Any]:
    """Parses a title into a category and a name.

    A build title should be in the format of:
    ```
    [Record Category] [component restrictions]+ <door size> [wiring placement restrictions]+ <door type> <orientation>
    ```

    Args:
        title: The title to parse

    Returns:
        A dictionary containing the parsed information.
    """
    data = {}
    words = title.split()
    if words[0].title() in RECORD_CATEGORIES:
        data["record_category"] = words.pop(0)

    if words[-1].title() not in DOOR_ORIENTATION_NAMES:
        raise ValueError(f"Invalid orientation. Expected one of {DOOR_ORIENTATION_NAMES}, found {words[-1]}")
    else:
        data["category"] = "Door"

    db = DatabaseManager()
    # Parse component restrictions
    component_restrictions = await db.table("restrictions").select("name").eq("build_category", data["category"]).eq("type", "component").execute()

