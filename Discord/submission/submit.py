import time
from datetime import datetime
from typing import Literal

import discord
from discord import InteractionResponse
from discord.ui import View
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context, has_any_role, hybrid_group, Cog, hybrid_command

import Discord.config
import Discord.utils as utils
import Discord.config as config
import Discord.submission.post as post
from Database.builds import get_all_builds_raw, get_builds, update_build, Build
import Database.message as msg
from Database.enums import Status

submission_roles = ['Admin', 'Moderator', 'Redstoner']
# TODO: Set up a webhook for the bot to handle google form submissions.

class SubmissionsCog(Cog, name='Submissions'):
    def __init__(self, bot):
        self.bot = bot

    @hybrid_group(name='submissions', invoke_without_command=True)
    async def submission_hybrid_group(self, ctx: Context):
        """View, confirm and deny submissions."""
        await ctx.send_help('submissions')

    @submission_hybrid_group.command(name='pending')
    async def get_pending_submissions(self, ctx: Context):
        """Shows an overview of all submissions pending review."""
        async with utils.RunningMessage(ctx) as sent_message:
            pending_submissions = [Build.from_dict(submission) for submission in await get_all_builds_raw(Status.PENDING)]

            if len(pending_submissions) == 0:
                desc = 'No open submissions.'
            else:
                desc = []
                for sub in pending_submissions:
                    # ID - Title
                    # by Creators - submitted by Submitter
                    desc.append(
                        f"**{sub.id}** - {sub.get_title()}\n_by {', '.join(sorted(sub.creators))}_ - _submitted by {sub.submitter_id}_")
                desc = '\n\n'.join(desc)

            em = utils.info_embed(title='Open Records', description=desc)
            await sent_message.edit(embed=em)

    @submission_hybrid_group.command(name='view')
    async def view_function(self, ctx: Context, submission_id: int):
        """Displays a submission."""
        async with utils.RunningMessage(ctx) as sent_message:
            submission = await Build.from_id(submission_id)

            if submission is None:
                error_embed = utils.error_embed('Error', 'No open submission with that ID.')
                return await sent_message.edit(embed=error_embed)

            return await sent_message.edit(embed=submission.generate_embed())

    @staticmethod
    def is_owner_server(ctx: Context):
        if not ctx.guild.id == config.OWNER_SERVER_ID:
            # TODO: Make a custom error for this.
            # https://discordpy.readthedocs.io/en/stable/ext/commands/api.html?highlight=is_owner#discord.discord.ext.commands.on_command_error
            raise commands.CommandError('This command can only be executed on certain servers.')
        return True

    @submission_hybrid_group.command(name='confirm')
    @commands.check(is_owner_server)
    @has_any_role(*submission_roles)
    async def confirm_function(self, ctx: Context, submission_id: int):
        """Marks a submission as confirmed.

        This posts the submission to all the servers which configured the bot."""
        async with utils.RunningMessage(ctx) as sent_message:
            build = await Build.from_id(submission_id)

            if build is None:
                error_embed = utils.error_embed('Error', 'No pending submission with that ID.')
                return await sent_message.edit(embed=error_embed)

            await build.confirm()
            await post.send_submission(self.bot, build)

            success_embed = utils.info_embed('Success', 'Submission has successfully been confirmed.')
            return await sent_message.edit(embed=success_embed)

    @submission_hybrid_group.command(name='deny')
    @commands.check(is_owner_server)
    @has_any_role(*submission_roles)
    async def deny_function(self, ctx: Context, submission_id: int):
        """Marks a submission as denied."""
        async with utils.RunningMessage(ctx) as sent_message:
            build = await Build.from_id(submission_id)

            if build is None:
                error_embed = utils.error_embed('Error', 'No pending submission with that ID.')
                return await sent_message.edit(embed=error_embed)

            await build.deny()

            success_embed = utils.info_embed('Success', 'Submission has successfully been denied.')
            return await sent_message.edit(embed=success_embed)

    @submission_hybrid_group.command(name='outdated')
    async def outdated_function(self, ctx: Context):
        """Shows an overview of all discord posts that require updating."""
        async with utils.RunningMessage(ctx) as sent_message:
            outdated_messages = await msg.get_outdated_messages(ctx.guild.id)

            if len(outdated_messages) == 0:
                desc = 'No outdated submissions.'
                em = utils.info_embed(title='Outdated Records', description=desc)
                return await sent_message.edit(embed=em)

            builds = await get_builds([message['build_id'] for message in outdated_messages])

            # TODO: Consider using get_unsent_messages too, and then merge the two lists, with different headers.
            # unsent_submissions = submissions.get_unsent_submissions(ctx.guild.id)

            desc = []
            for build in builds:
                desc.append(
                    f"**{build.id}** - {build.get_title()}\n_by {', '.join(sorted(build.creators))}_ - _submitted by {build.submitter_id}_")
            desc = '\n\n'.join(desc)

            em = discord.Embed(title='Outdated Records', description=desc, colour=utils.discord_green)
            return await sent_message.edit(embed=em)

    @submission_hybrid_group.command(name='update')
    @has_any_role(*submission_roles)
    async def update_function(self, ctx, submission_id: int):
        """Update or post an outdated discord post to this server."""
        async with utils.RunningMessage(ctx) as sent_message:
            message = await msg.get_outdated_message(ctx.guild.id, submission_id)

            if message is None:
                error_embed = utils.error_embed('Error', 'No outdated submissions with that ID.')
                return await sent_message.edit(embed=error_embed)

            # If message isn't yet tracked, add it.
            # await post.send_submission_to_server(self.bot, message[1], ctx.guild.id)

            await post.edit_post(self.bot, ctx.guild, message['channel_id'], message['message_id'], message['build_id'])

            success_embed = utils.info_embed('Success', 'Post has successfully been updated.')
            return await sent_message.edit(embed=success_embed)

    @submission_hybrid_group.command(name='update_all')
    @has_any_role(*submission_roles)
    async def update_all_function(self, ctx):
        """Updates all outdated discord posts in this server."""
        async with utils.RunningMessage(ctx) as sent_message:
            outdated_messages = await msg.get_outdated_messages(ctx.guild.id)

            for message in outdated_messages:
                # If message isn't yet tracked, add it.
                # await post.send_submission_to_server(self.bot, sub, ctx.guild.id)
                await post.edit_post(self.bot, ctx.guild, message['channel_id'], message['message_id'], message['build_id'])

            success_embed = utils.info_embed('Success', 'All posts have been successfully updated.')
            return await sent_message.edit(embed=success_embed)

    @hybrid_command(name='versions')
    async def versions(self, ctx: Context):
        """Shows a list of versions the bot recognizes."""
        await ctx.send(config.VERSIONS_LIST)

    @app_commands.command(name='submit')
    @app_commands.describe(
        record_category='The category of the build. If none, use "None".',
        door_width='The width of the door itself. Like 2x2 piston door.',
        door_height='The height of the door itself. Like 2x2 piston door.',
        pattern='The pattern type of the door. For example, "full lamp" or "funnel".',
        door_type='Door, Skydoor, or Trapdoor.',
        build_width='The width of the build.',
        build_height='The height of the build.',
        build_depth='The depth of the build.',
        works_in='The versions the build works in. Default to newest version. /versions for full list.',
        wiring_placement_restrictions='For example, "Seamless, Full Flush". See the regulations (/docs) for the complete list.',
        component_restrictions='For example, "No Pistons, No Slime Blocks". See the regulations (/docs) for the complete list.',
        information_about_build='Any additional information about the build.',
        normal_closing_time='The time it takes to close the door, in gameticks. (1s = 20gt)',
        normal_opening_time='The time it takes to open the door, in gameticks. (1s = 20gt)',
        date_of_creation='The date the build was created.',
        in_game_name_of_creator='The in-game name of the creator(s).',
        locationality='Whether the build works everywhere, or only in certain locations.',
        directionality='Whether the build works in all directions, or only in certain directions.',
        link_to_image='A link to an image of the build. Use direct links only. e.g."https://i.imgur.com/abc123.png"',
        link_to_youtube_video='A link to a video of the build.',
        link_to_world_download='A link to download the world.',
        server_ip='The IP of the server where the build is located.',
        coordinates='The coordinates of the build in the server.',
        command_to_get_to_build='The command to get to the build in the server.'
    )
    async def submit(self, interaction: discord.Interaction, record_category: Literal['Smallest', 'Fastest', 'First', 'None'],
                     door_width: int, door_height: int, pattern: str, door_type: Literal['Door', 'Skydoor', 'Trapdoor'],
                     build_width: int, build_height: int, build_depth: int,
                     # Optional parameters
                     works_in: str = Discord.config.VERSIONS_LIST[-1],
                     wiring_placement_restrictions: str = None,
                     component_restrictions: str = None, information_about_build: str = None,
                     normal_opening_time: int = None, normal_closing_time: int = None,
                     date_of_creation: str = None, in_game_name_of_creator: str = None,
                     locationality: Literal["Locational", "Locational with fixes"] = None,
                     directionality: Literal["Directional", "Directional with fixes"] = None,
                     link_to_image: str = None, link_to_youtube_video: str = None,
                     link_to_world_download: str = None, server_ip: str = None, coordinates: str = None,
                     command_to_get_to_build: str = None):
        """Submits a record to the database directly."""
        # FIXME: Discord WILL pass integers even if we specify a string. Need to convert them to strings.

        response: InteractionResponse = interaction.response  # type: ignore
        await response.defer()

        followup: discord.Webhook = interaction.followup  # type: ignore
        message: discord.WebhookMessage | None = await followup.send(embed=utils.info_embed('Working', 'Updating information...'))

        build = await Build.add({
            'record_category': record_category if record_category != 'None' else None,
            'submission_status': Status.PENDING,
            'door_width': door_width,
            'door_height': door_height,
            'pattern': pattern,
            'door_orientation_type': door_type,
            'wiring_placement_restrictions': wiring_placement_restrictions,
            'component_restrictions': component_restrictions,
            'information': information_about_build,
            'width': build_width,
            'height': build_height,
            'depth': build_depth,
            'normal_closing_time': normal_closing_time,
            'normal_opening_time': normal_opening_time,
            'visible_closing_time': None,  # TODO: Discord only allows 25 options. For now, ignore the absolute times.
            'visible_opening_time': None,
            'date_of_creation': date_of_creation,
            'submission_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'creators_ign': in_game_name_of_creator,
            'locationality': locationality,
            'directionality': directionality,
            'functional_versions': works_in,
            'image_url': link_to_image,
            'video_url': link_to_youtube_video,
            'world_download_url': link_to_world_download,
            'server_ip': server_ip,
            'coordinates': coordinates,
            'command_to_build': command_to_get_to_build,
            'submitter_id': str(interaction.user)
        })
        # Shows the submission to the user
        await followup.send("Here is a preview of the submission. Use /edit if you have made a mistake",
                            embed=build.generate_embed(), ephemeral=True)

        success_embed = utils.info_embed('Success', f'Build submitted successfully!\nThe submission ID is: {build.id}')
        await message.edit(embed=success_embed)
        await post.send_submission(self.bot, build)

    @app_commands.command(name='edit')
    @app_commands.describe(
        door_width='The width of the door itself. Like 2x2 piston door.',
        door_height='The height of the door itself. Like 2x2 piston door.',
        pattern='The pattern type of the door. For example, "full lamp" or "funnel".',
        door_type='Door, Skydoor, or Trapdoor.',
        build_width='The width of the build.',
        build_height='The height of the build.',
        build_depth='The depth of the build.',
        works_in='The versions the build works in. Default to newest version. /versions for full list.',
        wiring_placement_restrictions='For example, "Seamless, Full Flush". See the regulations (/docs) for the complete list.',
        component_restrictions='For example, "No Pistons, No Slime Blocks". See the regulations (/docs) for the complete list.',
        information_about_build='Any additional information about the build.',
        normal_closing_time='The time it takes to close the door, in gameticks. (1s = 20gt)',
        normal_opening_time='The time it takes to open the door, in gameticks. (1s = 20gt)',
        date_of_creation='The date the build was created.',
        in_game_name_of_creator='The in-game name of the creator(s).',
        locationality='Whether the build works everywhere, or only in certain locations.',
        directionality='Whether the build works in all directions, or only in certain directions.',
        link_to_image='A link to an image of the build. Use direct links only. e.g."https://i.imgur.com/abc123.png"',
        link_to_youtube_video='A link to a video of the build.',
        link_to_world_download='A link to download the world.',
        server_ip='The IP of the server where the build is located.',
        coordinates='The coordinates of the build in the server.',
        command_to_get_to_build='The command to get to the build in the server.'
    )
    async def edit(self, interaction: discord.Interaction, submission_id: int, door_width: int = None, door_height: int = None,
                   pattern: str = None, door_type: Literal['Door', 'Skydoor', 'Trapdoor'] = None, build_width: int = None,
                   build_height: int = None, build_depth: int = None, works_in: str = None, wiring_placement_restrictions: str = None,
                   component_restrictions: str = None, information_about_build: str = None,
                   normal_closing_time: int = None,
                   normal_opening_time: int = None, date_of_creation: str = None, in_game_name_of_creator: str = None,
                   locationality: Literal["Locational", "Locational with fixes"] = None,
                   directionality: Literal["Directional", "Directional with fixes"] = None,
                   link_to_image: str = None, link_to_youtube_video: str = None,
                   link_to_world_download: str = None, server_ip: str = None, coordinates: str = None,
                   command_to_get_to_build: str = None):
        """Edits a record in the database directly."""
        response: InteractionResponse = interaction.response  # type: ignore
        await response.defer()

        followup: discord.Webhook = interaction.followup  # type: ignore
        message: discord.WebhookMessage | None = await followup.send(embed=utils.info_embed('Working', 'Updating information...'))

        update_values = {
            'last_update': datetime.now().strftime(r'%Y-%m-%d %H:%M:%S.%f'),
            'door_width': door_width,
            'door_height': door_height,
            'pattern': pattern,
            'door_orientation_type': door_type,
            'wiring_placement_restrictions': wiring_placement_restrictions,
            'component_restrictions': component_restrictions,
            'information': information_about_build,
            'width': build_width,
            'height': build_height,
            'depth': build_depth,
            'normal_closing_time': normal_closing_time,
            'normal_opening_time': normal_opening_time,
            'date_of_creation': date_of_creation,
            'creators_ign': in_game_name_of_creator,
            'locationality': locationality,
            'directionality': directionality,
            'functional_versions': works_in,
            'image_url': link_to_image,
            'video_url': link_to_youtube_video,
            'world_download_url': link_to_world_download,
            'server_ip': server_ip,
            'coordinates': coordinates,
            'command_to_build': command_to_get_to_build,
            'submitter_id': None
        }
        update_values = {k: v for k, v in update_values.items() if v is not None}

        old_submission = await Build.from_id(submission_id)
        new_submission = Build.from_dict({**old_submission.to_dict(), **update_values})
        preview_embed = new_submission.generate_embed()

        # Show a preview of the changes and ask for confirmation
        await message.edit(embed=utils.info_embed('Waiting', 'User confirming changes...'))
        view = ConfirmationView()
        preview = await followup.send(embed=preview_embed, view=view, ephemeral=True, wait=True)
        await view.wait()

        await preview.delete()
        if view.value is None:
            await message.edit(embed=utils.info_embed('Timed out', 'Build edit canceled due to inactivity.'))
        elif view.value:
            await update_build(submission_id, update_values)
            await message.edit(embed=utils.info_embed('Success', 'Build edited successfully'))
        else:
            await message.edit(embed=utils.info_embed('Cancelled', 'Build edit canceled by user'))

class ConfirmationView(View):
    def __init__(self, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
