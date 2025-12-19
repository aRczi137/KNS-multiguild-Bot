import discord
from discord.ext import commands
from discord import app_commands

class PrivateChannels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_channels = {}  # user_id -> channel_id

    @app_commands.command(name="create_channel", description="Stwórz prywatny kanał tekstowy")
    async def create_channel(self, interaction: discord.Interaction):
        guild = interaction.guild
        author = interaction.user

        # sprawdzamy czy autor ma już swój kanał
        if author.id in self.active_channels:
            return await interaction.response.send_message("Masz już swój prywatny kanał!", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            author: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        # tutaj dodajemy kategorię po ID
        category_id = 1412528119419633704  
        category = guild.get_channel(category_id)

        channel = await guild.create_text_channel(
            name=f"prywatny-{author.name}",
            overwrites=overwrites,
            category=category,
            reason="Kanał prywatny"
        )

        self.active_channels[author.id] = channel.id
        await interaction.response.send_message(f"Stworzyłem Twój kanał w kategorii {category.name}: {channel.mention}", ephemeral=True)


    @app_commands.command(name="invite_channel", description="Zaproś kogoś do swojego prywatnego kanału")
    async def invite_channel(self, interaction: discord.Interaction, member: discord.Member):
        author = interaction.user

        if author.id not in self.active_channels:
            return await interaction.response.send_message("Nie masz jeszcze prywatnego kanału.", ephemeral=True)

        channel_id = self.active_channels[author.id]
        channel = interaction.guild.get_channel(channel_id)

        if not channel:
            return await interaction.response.send_message("Nie znaleziono Twojego kanału.", ephemeral=True)

        await channel.set_permissions(member, view_channel=True, send_messages=True)
        await interaction.response.send_message(f"Zaprosiłeś {member.mention} do {channel.mention}", ephemeral=True)

    @app_commands.command(name="delete_channel", description="Usuń swój prywatny kanał")
    async def delete_channel(self, interaction: discord.Interaction):
        author = interaction.user

        if author.id not in self.active_channels:
            return await interaction.response.send_message("Nie masz prywatnego kanału do usunięcia.", ephemeral=True)

        channel_id = self.active_channels.pop(author.id)
        channel = interaction.guild.get_channel(channel_id)

        if channel:
            await channel.delete(reason="Usunięto prywatny kanał")
            await interaction.response.send_message("Twój prywatny kanał został usunięty.", ephemeral=True)
        else:
            await interaction.response.send_message("Kanał już nie istnieje.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PrivateChannels(bot))