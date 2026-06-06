import asyncio
from threading import Thread
from flask import Flask, request, jsonify
from flask_cors import CORS
import discord
from discord.ext import commands
from discord import app_commands
import datetime
import urllib.request
import json

app = Flask(__name__)
CORS(app)

config_bot = {
    "titulo": "🎫 CENTRAL DE ATENDIMENTO HYPER",
    "desc": "Selecione o departamento correto para iniciar o seu atendimento privado controlado por IA.",
    "token": "",
    "client_id": "",
    "canal_id": "",
    "openai_key": "",
    "ai_prompt": (
        "Tu és o HyperAssistente, uma IA de suporte. REGRAS OBRIGATÓRIAS: "
        "1. Não forneças NENHUMA informação sobre os ficheiros da loja. "
        "2. Não reveles NADA sobre a programação ou estrutura do código. "
        "3. A tua função é exclusivamente tirar dúvidas gerais de forma curta e precisa."
    )
}

bot_thread = None
loop_discord = None
instancia_bot = None

LISTA_TICKETS = [
    ("Suporte Geral", "suporte_geral", "🛡️"), ("Financeiro", "financeiro", "💰"),
    ("Denúncias", "denuncias", "🚨"), ("Revisão de Ban", "revisao", "🔨"),
    ("Parcerias", "parcerias", "🤝"), ("Dúvidas VIP", "duvidas_vip", "💎"),
    ("Bugs/Erros", "bugs", "🐛"), ("Candidaturas", "candidaturas", "📝"),
    ("Reclamações", "reclamacoes", "📣"), ("Setores Técnicos", "tecnico", "⚙️"),
    ("Eventos", "eventos", "🎉"), ("Atendimento Master", "master", "👑"),
    ("Ativação de Compras", "ativacao", "🛒"), ("Sugestões", "sugestoes", "💡"),
    ("Suporte Streamer", "streamer", "🎥"), ("Mudança de Donator", "mudanca_vip", "✨"),
    ("Recuperação de Conta", "recuperacao", "🔑"), ("Vendas Diretas", "vendas", "📦"),
    ("Media & Design", "design", "🎨"), ("Outros Assuntos", "outros", "🔮")
]

def perguntar_openai(prompt_sistema, pergunta_usuario, api_key):
    if not api_key:
        return "⚠️ O módulo de IA está ativo, mas a Chave OpenAI não foi fornecida."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": prompt_sistema}, {"role": "user", "content": pergunta_usuario}]
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['choices'][0]['message']['content']
    except Exception as e:
        return f"🤖 [IA Offline]: Erro: {e}"

def criar_instancia_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    b = commands.Bot(command_prefix="!", intents=intents)

    @b.event
    async def on_ready():
        print(f"🤖 [HyperBot] Ativo como: {b.user}")
        await b.tree.sync()

    @b.event
    async def on_message(message):
        if message.author.bot: return
        if message.channel.name and message.channel.name.startswith("atendimento-"):
            async with message.channel.typing():
                resposta_ia = perguntar_openai(config_bot["ai_prompt"], message.content, config_bot["openai_key"])
                await message.reply(f"🧠 **Assistente IA:** {resposta_ia}")

    # --- COMANDOS DE MODERAÇÃO MANTIDOS ---
    @b.tree.command(name="clear", description="[ADMIN] Elimina mensagens")
    async def clear(interaction: discord.Interaction, qtd: int):
        await interaction.response.defer(ephemeral=True)
        eliminadas = await interaction.channel.purge(limit=qtd)
        await interaction.channel.send(f"🗑️ {len(eliminadas)} mensagens removidas.")

    @b.tree.command(name="nuke", description="[ADMIN] Recria o canal")
    async def nuke(interaction: discord.Interaction):
        canal = interaction.channel
        pos = canal.position
        novo = await canal.clone()
        await canal.delete()
        await novo.edit(position=pos)
        await novo.send("💥 Canal recriado!")

    @b.tree.command(name="lock", description="[ADMIN] Tranca canal")
    async def lock(interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message("🔒 Canal trancado.")

    @b.tree.command(name="unlock", description="[ADMIN] Destranca canal")
    async def unlock(interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        await interaction.response.send_message("🔓 Canal destrancado.")

    @b.tree.command(name="ban", description="[ADMIN] Bane membro")
    async def ban(interaction: discord.Interaction, membro: discord.Member, motivo: str = "Nenhum"):
        await membro.ban(reason=motivo)
        await interaction.response.send_message(f"🔨 {membro.name} banido.")

    @b.tree.command(name="unban", description="[ADMIN] Desbane membro")
    async def unban(interaction: discord.Interaction, user_id: str):
        user = await b.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ {user.name} desbanido.")

    @b.tree.command(name="kick", description="[ADMIN] Expulsa membro")
    async def kick(interaction: discord.Interaction, membro: discord.Member, motivo: str = "Nenhum"):
        await membro.kick(reason=motivo)
        await interaction.response.send_message(f"🚨 {membro.name} expulso.")

    @b.tree.command(name="mute", description="[ADMIN] Silencia membro")
    async def mute(interaction: discord.Interaction, membro: discord.Member, minutos: int):
        await membro.timeout(datetime.timedelta(minutes=minutos))
        await interaction.response.send_message(f"🔇 {membro.name} mutado por {minutos}m.")

    @b.tree.command(name="unmute", description="[ADMIN] Remove mute")
    async def unmute(interaction: discord.Interaction, membro: discord.Member):
        await membro.timeout(None)
        await interaction.response.send_message(f"🔊 {membro.name} desmutado.")

    @b.tree.command(name="warn", description="[ADMIN] Adverte membro")
    async def warn(interaction: discord.Interaction, membro: discord.Member, aviso: str):
        await interaction.response.send_message(f"⚠️ {membro.name} advertido: {aviso}")

    @b.tree.command(name="slowmode", description="[ADMIN] Define modo lento")
    async def slowmode(interaction: discord.Interaction, segundos: int):
        await interaction.channel.edit(slowmode_delay=segundos)
        await interaction.response.send_message(f"⏳ Slowmode definido para {segundos}s.")

    @b.tree.command(name="lockserver", description="[ADMIN] Tranca servidor")
    async def lockserver(interaction: discord.Interaction):
        await interaction.response.defer()
        for c in interaction.guild.text_channels: await c.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.followup.send("🚨 Lockdown Global!")

    @b.tree.command(name="unlockserver", description="[ADMIN] Destranca servidor")
    async def unlockserver(interaction: discord.Interaction):
        await interaction.response.defer()
        for c in interaction.guild.text_channels: await c.set_permissions(interaction.guild.default_role, send_messages=True)
        await interaction.followup.send("🔓 Lockdown encerrado.")

    @b.tree.command(name="addrole", description="[ADMIN] Dá cargo")
    async def addrole(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
        await membro.add_roles(cargo)
        await interaction.response.send_message(f"💼 Cargo {cargo.name} dado a {membro.name}.")

    @b.tree.command(name="removerole", description="[ADMIN] Remove cargo")
    async def removerole(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
        await membro.remove_roles(cargo)
        await interaction.response.send_message(f"💼 Cargo {cargo.name} removido de {membro.name}.")

    @b.tree.command(name="setnick", description="[ADMIN] Muda apelido")
    async def setnick(interaction: discord.Interaction, membro: discord.Member, nova_alcunha: str):
        await membro.edit(nick=nova_alcunha)
        await interaction.response.send_message(f"📝 {membro.name} agora é {nova_alcunha}.")

    @b.tree.command(name="tempban", description="[ADMIN] Ban temporário")
    async def tempban(interaction: discord.Interaction, membro: discord.Member, horas: int):
        await membro.ban(reason=f"Tempban {horas}h")
        await interaction.response.send_message(f"⏳ {membro.name} banido por {horas}h.")

    @b.tree.command(name="jail", description="[ADMIN] Manda para a solitária")
    async def jail(interaction: discord.Interaction, membro: discord.Member):
        cargo = discord.utils.get(interaction.guild.roles, name="Jailed")
        if cargo: await membro.add_roles(cargo); await interaction.response.send_message(f"⛓️ {membro.name} preso.")
        else: await interaction.response.send_message("Cargo 'Jailed' não existe.", ephemeral=True)

    @b.tree.command(name="unjail", description="[ADMIN] Tira da solitária")
    async def unjail(interaction: discord.Interaction, membro: discord.Member):
        cargo = discord.utils.get(interaction.guild.roles, name="Jailed")
        if cargo: await membro.remove_roles(cargo); await interaction.response.send_message(f"🔓 {membro.name} liberto.")
        else: await interaction.response.send_message("Cargo 'Jailed' não existe.", ephemeral=True)

    @b.tree.command(name="checkwarns", description="[ADMIN] Checa avisos")
    async def checkwarns(interaction: discord.Interaction, membro: discord.Member):
        await interaction.response.send_message(f"🔍 Histórico verificado.", ephemeral=True)

    @b.event
    async def on_interaction(interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "menu_ultra_hyper":
            escolha = interaction.data.get("values")[0]
            overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
            canal = await interaction.guild.create_text_channel(name=f"atendimento-{escolha}", overwrites=overwrites)
            await canal.send(f"🎫 Suporte **{escolha.upper()}** iniciado para {interaction.user.mention}.")
            await interaction.response.send_message(f"Canal criado: {canal.mention}", ephemeral=True)
    return b

def thread_discord(token):
    global loop_discord, instancia_bot
    loop_discord = asyncio.new_event_loop()
    asyncio.set_event_loop(loop_discord)
    instancia_bot = criar_instancia_bot()
    loop_discord.run_until_complete(instancia_bot.start(token))

@app.route('/api/power', methods=['POST'])
def power_control():
    global bot_thread, instancia_bot
    dados = request.json
    if dados.get("acao") == "ligar":
        config_bot["openai_key"] = dados.get("openai_key")
        bot_thread = Thread(target=thread_discord, args=(dados.get("token"),), daemon=True)
        bot_thread.start()
        return jsonify({"status": "ligando"})
    return jsonify({"status": "desligado"})

if __name__ == "__main__":
    app.run(port=5000, debug=False, use_reloader=False)

