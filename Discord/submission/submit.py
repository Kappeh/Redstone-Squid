from typing import Literal

import discord
from discord import InteractionResponse
from discord.ext import commands
from discord.ext.commands import Context, has_any_role, hybrid_group, Cog, hybrid_command, flag

import Database.message as msg
import Discord.config
import Discord.config as config
import Discord.submission.post as post
import Discord.utils as utils
from Database.builds import get_all_builds, get_builds, Build
from Database.enums import Status
from Discord.types import SubmissionCommandResponseT
from Discord.utils import ConfirmationView, RunningMessage

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
            pending_submissions = await get_all_builds(Status.PENDING)

            if len(pending_submissions) == 0:
                desc = 'No open submissions.'
            else:
                desc = []
                for sub in pending_submissions:
                    # ID - Title
                    # by Creators - submitted by Submitter
                    desc.append(
                        f"**{sub.id}** - {sub.get_title()}\n_by {', '.join(sorted(sub.creators_ign))}_ - _submitted by {sub.submitter_id}_")
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
            await post.post_build(self.bot, build)

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

    # @submission_hybrid_group.command("send_all")
    # @has_any_role(*submission_roles)
    async def send_all(self, ctx):
        """Sends all records and builds to this server, in the channels set."""
        # NOT in use right now
        async with utils.RunningMessage(ctx) as sent_message:
            unsent_builds = await msg.get_unsent_builds(ctx.guild.id)

            for build in unsent_builds:
                await post.post_build_to_server(self.bot, build, ctx.guild.id)

            success_embed = utils.info_embed('Success', 'All posts have been successfully sent.')
            return await sent_message.edit(embed=success_embed)

    @hybrid_command(name='versions')
    async def versions(self, ctx: Context):
        """Shows a list of versions the bot recognizes."""
        await ctx.send(config.VERSIONS_LIST)

    class SubmitFlags(commands.FlagConverter):
        """Parameters information for the /submit command."""
        door_size: str = flag(description='e.g. *2x2* piston door. In width x height (x depth), spaces optional.')
        record_category: Literal['Smallest', 'Fastest', 'First'] = flag(default=None, description='Is this build a record?')
        pattern: str = flag(default='Regular', description='The pattern type of the door. For example, "full lamp" or "funnel".')
        door_type: Literal['Door', 'Skydoor', 'Trapdoor'] = flag(default='Door', description='Door, Skydoor, or Trapdoor.')
        build_width: int = flag(default=None, description='The width of the build.')
        build_height: int = flag(default=None, description='The height of the build.')
        build_depth: int = flag(default=None, description='The depth of the build.')
        works_in: str = flag(default=Discord.config.VERSIONS_LIST[-1], description='The versions the build works in. Default to newest version. /versions for full list.')
        wiring_placement_restrictions: str = flag(default=None, description='For example, "Seamless, Full Flush". See the regulations (/docs) for the complete list.')
        component_restrictions: str = flag(default=None, description='For example, "No Pistons, No Slime Blocks". See the regulations (/docs) for the complete list.')
        information_about_build: str = flag(default=None, description='Any additional information about the build.')
        normal_closing_time: int = flag(default=None, description='The time it takes to close the door, in gameticks. (1s = 20gt)')
        normal_opening_time: int = flag(default=None, description='The time it takes to open the door, in gameticks. (1s = 20gt)')
        date_of_creation: str = flag(default=None, description='The date the build was created.')
        in_game_name_of_creator: str = flag(default=None, description='The in-game name of the creator(s).')
        locationality: Literal["Locational", "Locational with fixes"] = flag(default=None, description='Whether the build works everywhere, or only in certain locations.')
        directionality: Literal["Directional", "Directional with fixes"] = flag(default=None, description='Whether the build works in all directions, or only in certain directions.')
        link_to_image: str = flag(default=None, description='A link to an image of the build. Use direct links only. e.g."https://i.imgur.com/abc123.png"')
        link_to_youtube_video: str = flag(default=None, description='A link to a video of the build.')
        link_to_world_download: str = flag(default=None, description='A link to download the world.')
        server_ip: str = flag(default=None, description='The IP of the server where the build is located.')
        coordinates: str = flag(default=None, description='The coordinates of the build in the server.')
        command_to_get_to_build: str = flag(default=None, description='The command to get to the build in the server.')

    @commands.hybrid_command(name='submit')
    async def submit(self, ctx: Context, flags: SubmitFlags):
        """Submits a record to the database directly."""
        # TODO: Discord only allows 25 options. Split this into multiple commands.
        # FIXME: Discord WILL pass integers even if we specify a string. Need to convert them to strings.
        interaction: discord.Interaction = ctx.interaction
        response: InteractionResponse = interaction.response  # type: ignore
        await response.defer()

        followup: discord.Webhook = interaction.followup  # type: ignore

        async with RunningMessage(followup) as message:
            fmt_data = format_submission_input(ctx, dict(flags))
            build = Build.from_dict(fmt_data)

            # TODO: Stop hardcoding this
            build.category = 'Door'
            build.submission_status = Status.PENDING

            await build.save()
            # Shows the submission to the user
            await followup.send("Here is a preview of the submission. Use /edit if you have made a mistake",
                                embed=build.generate_embed(), ephemeral=True)

            success_embed = utils.info_embed('Success', f'Build submitted successfully!\nThe submission ID is: {build.id}')
            await message.edit(embed=success_embed)
            await post.post_build(self.bot, build)

    class EditFlags(commands.FlagConverter):
        """Parameters information for the /edit command."""
        submission_id: int = flag(description='The ID of the submission to edit.')
        door_width: int = flag(default=None, description='The width of the door itself. Like 2x2 piston door.')
        door_height: int = flag(default=None, description='The height of the door itself. Like 2x2 piston door.')
        pattern: str = flag(default=None, description='The pattern type of the door. For example, "full lamp" or "funnel".')
        door_type: Literal['Door', 'Skydoor', 'Trapdoor'] = flag(default=None, description='Door, Skydoor, or Trapdoor.')
        build_width: int = flag(default=None, description='The width of the build.')
        build_height: int = flag(default=None, description='The height of the build.')
        build_depth: int = flag(default=None, description='The depth of the build.')
        works_in: str = flag(default=None, description='The versions the build works in. Default to newest version. /versions for full list.')
        wiring_placement_restrictions: str = flag(default=None, description='For example, "Seamless, Full Flush". See the regulations (/docs) for the complete list.')
        component_restrictions: str = flag(default=None, description='For example, "No Pistons, No Slime Blocks". See the regulations (/docs) for the complete list.')
        information_about_build: str = flag(default=None, description='Any additional information about the build.')
        normal_closing_time: int = flag(default=None, description='The time it takes to close the door, in gameticks. (1s = 20gt)')
        normal_opening_time: int = flag(default=None, description='The time it takes to open the door, in gameticks. (1s = 20gt)')
        date_of_creation: str = flag(default=None, description='The date the build was created.')
        in_game_name_of_creator: str = flag(default=None, description='The in-game name of the creator(s).')
        locationality: Literal["Locational", "Locational with fixes"] = flag(default=None, description='Whether the build works everywhere, or only in certain locations.')
        directionality: Literal["Directional", "Directional with fixes"] = flag(default=None, description='Whether the build works in all directions, or only in certain directions.')
        link_to_image: str = flag(default=None, description='A link to an image of the build. Use direct links only. e.g."https://i.imgur.com/abc123.png"')
        link_to_youtube_video: str = flag(default=None, description='A link to a video of the build.')
        link_to_world_download: str = flag(default=None, description='A link to download the world.')
        server_ip: str = flag(default=None, description='The IP of the server where the build is located.')
        coordinates: str = flag(default=None, description='The coordinates of the build in the server.')
        command_to_get_to_build: str = flag(default=None, description='The command to get to the build in the server.')

    @commands.hybrid_command(name='edit')
    async def edit(self, ctx: Context, flags: EditFlags):
        """Edits a record in the database directly."""
        interaction: discord.Interaction = ctx.interaction
        response: InteractionResponse = interaction.response  # type: ignore
        await response.defer()

        followup: discord.Webhook = interaction.followup  # type: ignore
        async with RunningMessage(followup) as sent_message:
            submission = await Build.from_id(flags.submission_id)
            if submission is None:
                error_embed = utils.error_embed('Error', 'No submission with that ID.')
                return await sent_message.edit(embed=error_embed)

            update_values = format_submission_input(ctx, dict(flags))
            submission.update_local(update_values)
            preview_embed = submission.generate_embed()

            # Show a preview of the changes and ask for confirmation
            await sent_message.edit(embed=utils.info_embed('Waiting', 'User confirming changes...'))
            view = ConfirmationView()
            preview = await followup.send(embed=preview_embed, view=view, ephemeral=True, wait=True)
            await view.wait()

            await preview.delete()
            if view.value is None:
                await sent_message.edit(embed=utils.info_embed('Timed out', 'Build edit canceled due to inactivity.'))
            elif view.value:
                await sent_message.edit(embed=utils.info_embed('Editing', 'Editing build...'))
                await submission.save()
                await post.update_build_posts(self.bot, submission)
                await sent_message.edit(embed=utils.info_embed('Success', 'Build edited successfully'))
            else:
                await sent_message.edit(embed=utils.info_embed('Cancelled', 'Build edit canceled by user'))


def format_submission_input(ctx: Context, data: SubmissionCommandResponseT) -> dict:
    """Formats the submission data from what is passed in commands to something recognizable by Build."""
    # Union of all the /submit and /edit command options
    parsable_signatures = SubmissionCommandResponseT.__annotations__.keys()
    if not all(key in parsable_signatures for key in data):
        unknown_keys = [key for key in data if key not in parsable_signatures]
        raise ValueError(f"found unknown keys {unknown_keys} in data, did the command signature of /submit or /edit change?")

    fmt_data = dict()
    fmt_data['id'] = data.get('submission_id')
    # fmt_data['submission_status']

    fmt_data['record_category'] = data['record_category']
    if data.get('works_in') is not None:
        fmt_data['functional_versions'] = data['works_in'].split(", ")
    else:
        fmt_data['functional_versions'] = []

    fmt_data['width'] = data.get('build_width')
    fmt_data['height'] = data.get('build_height')
    fmt_data['depth'] = data.get('build_depth')

    if data.get('door_size'):
        width, height, depth = utils.parse_door_size(data['door_size'])
        fmt_data['door_width'] = width
        fmt_data['door_height'] = height
        fmt_data['door_depth'] = depth
    else:
        fmt_data['door_width'] = data.get('door_width')
        fmt_data['door_height'] = data.get('door_height')
    # fmt_data['door_depth']

    if data.get('pattern'):
        fmt_data['door_type'] = data.get('pattern').split(', ')
    fmt_data['door_orientation_type'] = data.get('door_type')

    if data.get('wiring_placement_restrictions') is not None:
        fmt_data['wiring_placement_restrictions'] = data['wiring_placement_restrictions'].split(", ")
    else:
        fmt_data['wiring_placement_restrictions'] = []
    if data.get('component_restrictions') is not None:
        fmt_data['component_restrictions'] = data['component_restrictions'].split(", ")
    else:
        fmt_data['component_restrictions'] = []
    misc_restrictions = [data.get('locationality'), data.get('directionality')]
    fmt_data['miscellaneous_restrictions'] = [x for x in misc_restrictions if x is not None]

    fmt_data['normal_closing_time'] = data.get('normal_closing_time')
    fmt_data['normal_opening_time'] = data.get('normal_opening_time')
    # fmt_data['visible_closing_time']
    # fmt_data['visible_opening_time']

    information_dict = {"user": data.get('information_about_build')} if data.get('information_about_build') is not None else None
    fmt_data['information'] = information_dict
    if data.get('in_game_name_of_creator') is not None:
        fmt_data['creators_ign'] = data['in_game_name_of_creator'].split(", ")
    else:
        fmt_data['creators_ign'] = []

    fmt_data['image_url'] = data.get('link_to_image')
    fmt_data['video_url'] = data.get('link_to_youtube_video')
    fmt_data['world_download_url'] = data.get('link_to_world_download')

    fmt_data['server_ip'] = data.get('server_ip')
    fmt_data['coordinates'] = data.get('coordinates')
    fmt_data['command'] = data.get('command_to_get_to_build')

    fmt_data['submitter_id'] = ctx.author.id
    fmt_data['completion_time'] = data.get('date_of_creation')
    # fmt_data['edited_time'] = get_current_utc()

    fmt_data = {k: v for k, v in fmt_data.items() if v is not None}
    return fmt_data
