"""Handles user data and operations."""
import requests

from utils import utcnow
from database import DatabaseManager


async def add_user(user_id: int = None, ign: str = None) -> int:
    """Add a user to the database.

    Args:
        user_id: The user's Discord ID.
        ign: The user's in-game name.

    Returns:
        The ID of the new user.
    """
    if user_id is None and ign is None:
        raise ValueError("No user data provided.")

    db = DatabaseManager()
    response = await db.table("users").insert({"discord_id": user_id, "ign": ign}).execute()
    return response.data[0]["id"]


async def link_minecraft_account(user_id: int, code: str) -> bool:
    """Using a verification code, link a user's Discord account with their Minecraft account.

    Args:
        user_id: The user's Discord ID.
        code: The verification code.

    Returns:
        True if the code is valid and the accounts are linked, False otherwise.
    """
    db = DatabaseManager()

    response = await db.table("verification_codes").select("minecraft_uuid").eq("code", code).gt("expires", utcnow()).execute()
    if not response.data:
        return False
    minecraft_uuid = response.data[0]["minecraft_uuid"]

    # TODO: This currently does not check if the ign is already in use without a UUID or discord ID given.
    response = await db.table("users").update({"minecraft_uuid": minecraft_uuid, "ign": get_minecraft_username(minecraft_uuid)}).eq("discord_id", user_id).execute()
    if not response.data:
        await db.table("users").insert({"discord_id": user_id, "minecraft_uuid": minecraft_uuid, "ign": get_minecraft_username(minecraft_uuid)}).execute()
    return True


async def unlink_minecraft_account(user_id: int) -> bool:
    """Unlink a user's Minecraft account from their Discord account.

    Args:
        user_id: The user's Discord ID.

    Returns:
        True if the accounts were successfully unlinked, False otherwise.
    """
    db = DatabaseManager()
    await db.table("users").update({"minecraft_uuid": None}).eq("discord_id", user_id).execute()
    return True


def get_minecraft_username(user_uuid: str) -> str:
    """Get a user's Minecraft username from their UUID.

    Args:
        user_uuid: The user's Minecraft UUID.

    Returns:
        The user's Minecraft username.
    """
    # https://wiki.vg/Mojang_API#UUID_to_Profile_and_Skin.2FCape
    response = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{user_uuid}")
    return response.json()["name"]
