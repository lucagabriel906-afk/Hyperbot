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

# O prompt inicial foi atualizado com as regras rígidas solicitadas
config_bot = {
    "titulo": "🎫 CENTRAL DE ATENDIMENTO HYPER",
    "desc": "Selecione o departamento correto para iniciar o seu atendimento privado controlado por IA.",
    "token": "",
    "client_id": "",
    "canal_id": "",
    "openai_key": "",
    "ai_prompt": "Tu és o HyperAssistente, uma inteligência artificial integrada de suporte. Responda de forma educada, curta, precisa e direta às dúvidas dos membros no canal de ticket aberto. REGRAS IMPORTANTES E OBRIGATÓRIAS: Não informe absolutamente nada sobre os arquivos da loja. Não fale nada sobre a programação ou estrutura interna do código. Sua única função permitida é apenas tirar dúvidas gerais dos membros."
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

# Função para realizar chamadas à API da OpenAI via HTTP nativo com as regras aplicadas
def perguntar_openai(prompt_sistema, pergunta_usuario, api_key):
    if not api_key:
        return "⚠️ O módulo de Inteligência Artificial está ativo, mas nenhuma Chave OpenAI foi configurada no painel."
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": pergunta_usuario}
        ]
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['choices'][0]['message']['content']
    except Exception as e:
        return f"🤖 [IA Offline]: Não consegui processar o pedido. Detalhe: {e}"

def criar_instancia_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    b = commands.Bot(command_prefix="!", intents=intents)

    @b.event
    async def on_ready():
        print(f"🤖 [HyperBot] Ativo como: {b.user}")
        await b.tree.sync()

    # MONITORA MENSAGENS PARA RESPONDER EXCLUSIVAMENTE DENTRO DE TICKETS USANDO IA
    @b.event
    async def on_message(message):
        if message.author.bot:
            return
        
        # Verifica se é um canal de atendimento criado pelo sistema
        if message.channel.name and message.channel.name.startswith("atendimento-"):
            async with message.channel.typing():
                resposta_ia = perguntar_openai(
                    config_bot["ai_prompt"], 
                    message.content, 
                    config_bot["openai_key"]
                )
                await message.reply(f"🧠 **Assistente IA:** {resposta_ia}")

    # --- COMANDO MANUAL DO PAINEL ---
    @b.tree.command(name="painel", description="[ADMIN] Gera o menu de 20 categorias de suporte no canal atual")
    @app_commands.default_permissions(administrator=True)
    async def painel(interaction: discord.Interaction):
        embed = discord.Embed(title=config_bot["titulo"], description=config_bot["desc"], color=discord.Color.from_str("#6366F1"))
        select = discord.ui.Select(custom_id="menu_ultra_hyper", placeholder="🎯 Selecione uma das 20 categorias de suporte...")
        for label, value, emoji in LISTA_TICKETS:
            select.add_options([discord.SelectOption(label=label, value=value, emoji=emoji)])
        view = discord.ui.View(timeout=None)
        view.add_item(select)
        await interaction.response.send_message(embed=embed, view=view)

    # --- MANUTENÇÃO RIGOROSA DOS 20 COMANDOS DE MODERAÇÃO ---
    @b.tree.command(name="clear", description="[ADMIN] Elimina mensagens em massa do canal")
    @app_commands.default_permissions(administrator=True)
    async def clear(interaction: discord.Interaction, qtd: int):
        await interaction.response.defer(ephemeral=True)
        eliminadas = await interaction.channel.purge(limit=qtd)
        await interaction.channel.send(f"🗑️ **Mensagens Limpas:** O administrador {interaction.user.mention} eliminou `{len(eliminadas)}` mensagens.")

    @b.tree.command(name="nuke", description="[ADMIN] Recria o canal atual limpando todo o histórico")
    @app_commands.default_permissions(administrator=True)
    async def nuke(interaction: discord.Interaction):
        canal_atual = interaction.channel
        posicao = canal_atual.position
        novo_canal = await canal_atual.clone()
        await canal_atual.delete()
        await novo_canal.edit(position=posicao)
        await novo_canal.send(f"💥 **NUKE:** Canal totalmente recriado pelo administrador {interaction.user.mention}!")

    @b.tree.command(name="lock", description="[ADMIN] Bloqueia o envio de mensagens no canal")
    @app_commands.default_permissions(administrator=True)
    async def lock(interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(f"🔒 **Canal Trancado:** Bloqueado pelo administrador {interaction.user.mention}.")

    @b.tree.command(name="unlock", description="[ADMIN] Desbloqueia o envio de mensagens no canal")
    @app_commands.default_permissions(administrator=True)
    async def unlock(interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        await interaction.response.send_message(f"🔓 **Canal Destrancado:** Libertado pelo administrador {interaction.user.mention}.")

    @b.tree.command(name="ban", description="[ADMIN] Bane um utilizador permanentemente")
    @app_commands.default_permissions(administrator=True)
    async def ban(interaction: discord.Interaction, membro: discord.Member, motivo: str = "Nenhum"):
        await membro.ban(reason=motivo)
        await interaction.response.send_message(f"🔨 **Utilizador Banido:** {membro.mention} por {interaction.user.mention}. Motivo: `{motivo}`")

    @b.tree.command(name="unban", description="[ADMIN] Desbane um utilizador do servidor")
    @app_commands.default_permissions(administrator=True)
    async def unban(interaction: discord.Interaction, user_id: str):
        usuario = await b.fetch_user(int(user_id))
        await interaction.guild.unban(usuario)
        await interaction.response.send_message(f"✅ **Revogação de Ban:** O administrador {interaction.user.mention} desbaniu {usuario.name}.")

    @b.tree.command(name="kick", description="[ADMIN] Expulsa um membro do servidor")
    @app_commands.default_permissions(administrator=True)
    async def kick(interaction: discord.Interaction, membro: discord.Member, motivo: str = "Nenhum"):
        await membro.kick(reason=motivo)
        await interaction.response.send_message(f"🚨 **Expulsão:** {membro.mention} expulso por {interaction.user.mention}. Motivo: `{motivo}`")

    @b.tree.command(name="mute", description="[ADMIN] Silencia temporariamente um membro")
    @app_commands.default_permissions(administrator=True)
    async def mute(interaction: discord.Interaction, membro: discord.Member, minutos: int):
        await membro.timeout(datetime.timedelta(minutes=minutos))
        await interaction.response.send_message(f"🔇 **Silenciado:** {membro.mention} silenciado por {minutos}m por {interaction.user.mention}.")

    @b.tree.command(name="unmute", description="[ADMIN] Remove o silenciamento de um membro")
    @app_commands.default_permissions(administrator=True)
    async def unmute(interaction: discord.Interaction, membro: discord.Member):
        await membro.timeout(None)
        await interaction.response.send_message(f"🔊 **Silenciamento Removido:** {membro.mention} reabilitado por {interaction.user.mention}.")

    @b.tree.command(name="warn", description="[ADMIN] Aplica uma advertência formal")
    @app_commands.default_permissions(administrator=True)
    async def warn(interaction: discord.Interaction, membro: discord.Member, aviso: str):
        await interaction.response.send_message(f"⚠️ **Advertência:** {membro.mention} avisado por {interaction.user.mention}. Motivo: `{aviso}`")

    @b.tree.command(name="slowmode", description="[ADMIN] Define o modo lento")
    @app_commands.default_permissions(administrator=True)
    async def slowmode(interaction: discord.Interaction, segundos: int):
        await interaction.channel.edit(slowmode_delay=segundos)
        await interaction.response.send_message(f"⏳ **Modo Lento:** Tempo definido para `{segundos}s` por {interaction.user.mention}.")

    @b.tree.command(name="lockserver", description="[ADMIN] Tranca todo o servidor")
    @app_commands.default_permissions(administrator=True)
    async def lockserver(interaction: discord.Interaction):
        await interaction.response.defer()
        for canal in interaction.guild.text_channels:
            await canal.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.followup.send(f"🚨 **Lockdown Global:** Servidor trancado por {interaction.user.mention}!")

    @b.tree.command(name="unlockserver", description="[ADMIN] Destranca todo o servidor")
    @app_commands.default_permissions(administrator=True)
    async def unlockserver(interaction: discord.Interaction):
        await interaction.response.defer()
        for canal in interaction.guild.text_channels:
            await canal.set_permissions(interaction.guild.default_role, send_messages=True)
        await interaction.followup.send(f"🔓 **Fim do Lockdown:** Comunicação restaurada por {interaction.user.mention}!")

    @b.tree.command(name="addrole", description="[ADMIN] Atribui um cargo")
    @app_commands.default_permissions(administrator=True)
    async def addrole(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
        await membro.add_roles(cargo)
        await interaction.response.send_message(f"💼 **Cargo Adicionado:** {cargo.mention} dado a {membro.mention} por {interaction.user.mention}.")

    @b.tree.command(name="removerole", description="[ADMIN] Remove um cargo")
    @app_commands.default_permissions(administrator=True)
    async def removerole(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
        await membro.remove_roles(cargo)
        await interaction.response.send_message(f"💼 **Cargo Removido:** {cargo.mention} retirado de {membro.mention} por {interaction.user.mention}.")

    @b.tree.command(name="setnick", description="[ADMIN] Altera a alcunha")
    @app_commands.default_permissions(administrator=True)
    async def setnick(interaction: discord.Interaction, membro: discord.Member, nova_alcunha: str):
        await membro.edit(nick=nova_alcunha)
        await interaction.response.send_message(f"📝 **Alcunha Alterada:** {membro.mention} renomeado por {interaction.user.mention}.")

    @b.tree.command(name="tempban", description="[ADMIN] Banimento temporário")
    @app_commands.default_permissions(administrator=True)
    async def tempban(interaction: discord.Interaction, membro: discord.Member, horas: int):
        await membro.ban(reason=f"Tempban {horas}h")
        await interaction.response.send_message(f"⏳ **Ban Temporário:** {membro.mention} banido por `{horas} horas` por {interaction.user.mention}.")

    @b.tree.command(name="jail", description="[ADMIN] Envia para a solitária")
    @app_commands.default_permissions(administrator=True)
    async def jail(interaction: discord.Interaction, membro: discord.Member):
        cargo = discord.utils.get(interaction.guild.roles, name="Jailed")
        if cargo:
            await membro.add_roles(cargo)
            await interaction.response.send_message(f"⛓️ **Prisão:** {membro.mention} enviado para a solitária por {interaction.user.mention}.")
        else:
            await interaction.response.send_message("Cria um cargo `Jailed` primeiro.", ephemeral=True)

    @b.tree.command(name="unjail", description="[ADMIN] Remove da solitária")
    @app_commands.default_permissions(administrator=True)
    async def unjail(interaction: discord.Interaction, membro: discord.Member):
        cargo = discord.utils.get(interaction.guild.roles, name="Jailed")
        if cargo:
            await membro.remove_roles(cargo)
            await interaction.response.send_message(f"🔓 **Liberdade:** {membro.mention} libertado por {interaction.user.mention}.")

    @b.tree.command(name="checkwarns", description="[ADMIN] Analisa avisos")
    @app_commands.default_permissions(administrator=True)
    async def checkwarns(interaction: discord.Interaction, membro: discord.Member):
        await interaction.response.send_message(f"🔍 **Auditoria:** Histórico verificado por {interaction.user.mention}.", ephemeral=True)

    # --- COMPONENTE INTERATIVO DE SELEÇÃO DE TICKETS ---
    @b.event
    async def on_interaction(interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "menu_ultra_hyper":
            escolha = interaction.data.get("values")[0]
            guild = interaction.guild
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            canal = await guild.create_text_channel(name=f"atendimento-{escolha}", overwrites=overwrites)
            await canal.send(f"🎫 **Suporte Iniciado:** Olá {interaction.user.mention}, este canal é dedicado a **{escolha.upper()}**.\\n🤖 **Módulo de Inteligência Artificial Ativo!** Digite a sua dúvida e a IA responderá em instantes.")
            await interaction.response.send_message(f"Canal de ticket aberto com sucesso: {canal.mention}", ephemeral=True)

    return b

def thread_discord(token):
    global loop_discord, instancia_bot
    loop_discord = asyncio.new_event_loop()
    asyncio.set_event_loop(loop_discord)
    instancia_bot = criar_instancia_bot()
    try:
        loop_discord.run_until_complete(instancia_bot.start(token))
    except Exception as e:
        print(f"Erro ao ligar o bot: {e}")

@app.route('/api/power', methods=['POST'])
def power_control():
    global bot_thread, instancia_bot, loop_discord
    dados = request.json
    acao = dados.get("acao")
    
    if acao == "ligar":
        token = dados.get("token")
        if instancia_bot and not instancia_bot.is_closed():
            return jsonify({"status": "ja_ligado"})
        
        config_bot["token"] = token
        config_bot["client_id"] = dados.get("client_id")
        # Injeta automaticamente sua chave enviada caso ela esteja ativa
        config_bot["openai_key"] = dados.get("openai_key") or "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"
        
        bot_thread = Thread(target=thread_discord, args=(token,), daemon=True)
        bot_thread.start()
        return jsonify({"status": "ligando"})
        
    elif acao == "desligar":
        if instancia_bot and not instancia_bot.is_closed():
            future = asyncio.run_coroutine_threadsafe(instancia_bot.close(), loop_discord)
            future.result()
        return jsonify({"status": "desligado"})

@app.route('/api/status', methods=['GET'])
def get_bot_status():
    is_online = instancia_bot is not None and instancia_bot.is_ready() and not instancia_bot.is_closed()
    return jsonify({"online": is_online})

@app.route('/api/config-ultra', methods=['POST'])
def atualizar_config():
    global loop_discord, instancia_bot
    dados = request.json
    config_bot["titulo"] = dados.get("titulo", config_bot["titulo"])
    config_bot["desc"] = dados.get("descricao", config_bot["desc"])
    config_bot["canal_id"] = dados.get("canal_id", "")
    config_bot["ai_prompt"] = dados.get("ai_prompt", config_bot["ai_prompt"])
    
    # Se houver um Canal ID inserido, envia de forma automatizada o painel completo para lá
    if config_bot["canal_id"]:
        if instancia_bot and instancia_bot.is_ready():
            try:
                cid = int(config_bot["canal_id"])
                
                async def disparar_painel():
                    canal = instancia_bot.get_channel(cid)
                    if canal:
                        embed = discord.Embed(title=config_bot["titulo"], description=config_bot["desc"], color=discord.Color.from_str("#6366F1"))
                        select = discord.ui.Select(custom_id="menu_ultra_hyper", placeholder="🎯 Selecione uma das 20 categorias de suporte...")
                        for label, value, emoji in LISTA_TICKETS:
                            select.add_options([discord.SelectOption(label=label, value=value, emoji=emoji)])
                        view = discord.ui.View(timeout=None)
                        view.add_item(select)
                        await canal.send(embed=embed, view=view)
                        return True
                    return False

                fut = asyncio.run_coroutine_threadsafe(disparar_painel(), loop_discord)
                sucesso = fut.result()
                if not sucesso:
                    return jsonify({"status": "erro", "mensagem": "Canal não encontrado. Verifique se o ID está correto e se o bot faz parte do servidor correspondente."})
            except Exception as e:
                return jsonify({"status": "erro", "mensagem": f"Erro interno ao injetar painel no canal: {e}"})
        else:
            return jsonify({"status": "erro", "mensagem": "Configurações guardadas, mas o painel não foi enviado porque o Bot está offline. Ligue o painel primeiro!"})

    return jsonify({"status": "sucesso"})

if __name__ == "__main__":
    app.run(port=5000, debug=False, use_reloader=False)

