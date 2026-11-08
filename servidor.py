# =====================================================================
# servidor.py  -  SERVIDOR DO SISTEMA DE VENDA DE INGRESSOS (gRPC)
# =====================================================================
# O que este programa faz:
#   1. Abre uma "porta" de rede (50051) e fica esperando clientes.
#   2. Quando um cliente chama uma função remota (ex.: ComprarIngresso),
#      o gRPC recebe os bytes pela rede, transforma de volta em objeto
#      Python e chama o método correspondente da classe VendaIngressos.
#   3. O método aplica as regras do negócio, salva em dados.json e
#      devolve uma resposta, que o gRPC transforma em bytes e envia de volta.
#
# Como rodar:
#   python servidor.py              -> modo normal (com trava, correto)
#   python servidor.py --sem-trava  -> modo DEMONSTRAÇÃO do bug de concorrência
# =====================================================================

# ---------------------------------------------------------------------
# IMPORTAÇÕES
# ---------------------------------------------------------------------
import json          # para ler e gravar o arquivo dados.json
import os            # para verificar se o arquivo dados.json já existe
import socket        # só para descobrir o IP desta máquina e mostrar na tela
import sys           # para ler os argumentos da linha de comando (--sem-trava)
import threading     # para criar as "travas" (locks) entre threads
import time          # para simular o tempo de processamento do pagamento
import contextlib    # para criar uma "trava falsa" no modo --sem-trava
from concurrent import futures   # pool de threads que o gRPC usa para atender clientes
from datetime import datetime    # para comparar datas (evento já aconteceu?)

import grpc                  # a biblioteca gRPC em si (rede, HTTP/2, conexões)
import ingressos_pb2         # GERADO a partir do .proto: as classes das mensagens
import ingressos_pb2_grpc    # GERADO a partir do .proto: o esqueleto do servidor (stub)

# ---------------------------------------------------------------------
# CONFIGURAÇÕES
# ---------------------------------------------------------------------
# A porta é o "número do apartamento": o IP leva até esta máquina e a porta
# diz ao sistema operacional QUAL programa recebe os dados. 50051 é a porta
# que a documentação do gRPC costuma usar nos exemplos; poderia ser outra
# acima de 1024 (as abaixo de 1024 exigem administrador no Linux).
PORTA = 50051

ARQUIVO_DADOS = "dados.json"     # onde os dados ficam guardados entre execuções
FORMATO_DATA = "%Y-%m-%d %H:%M"  # formato das datas, ex.: 2026-12-05 20:00
TEMPO_PAGAMENTO = 0.2            # segundos "processando o pagamento" (simulação)

# Se o servidor for iniciado com --sem-trava, desligamos a trava da venda
# para mostrar na apresentação o que acontece sem sincronização.
USAR_TRAVA_VENDA = "--sem-trava" not in sys.argv

# ---------------------------------------------------------------------
# AS DUAS TRAVAS (LOCKS)
# ---------------------------------------------------------------------
# O gRPC atende vários clientes AO MESMO TEMPO, cada um numa thread.
# Threads compartilham a mesma memória (o dicionário "dados"), então
# precisamos organizar quem mexe nele e quando.
#
# trava_dados: protege o dicionário e o arquivo. Garante que duas threads
#   nunca escrevam ao mesmo tempo (seria como duas pessoas escrevendo na
#   mesma linha de um caderno). Fica SEMPRE ligada.
trava_dados = threading.RLock()

# trava_venda: garante que "verificar se o assento está livre" e "registrar
#   a venda" aconteçam JUNTOS, sem ninguém no meio. É a que demonstramos.
#   No modo --sem-trava ela vira uma trava falsa (nullcontext), que não trava nada.
trava_venda = threading.Lock() if USAR_TRAVA_VENDA else contextlib.nullcontext()


# =====================================================================
# PARTE 1 - ARMAZENAMENTO (dados em memória + arquivo JSON)
# =====================================================================
# O enunciado pede para "armazenar os dados de forma simples". Usamos um
# dicionário Python na memória (rápido) e, a cada alteração, gravamos tudo
# em dados.json (para não perder nada se o servidor for desligado).

def dados_iniciais():
    """Cria alguns eventos de exemplo para a demonstração."""
    return {
        "proximo_id_evento": 5,
        "proximo_id_ingresso": 1,
        # As chaves são strings porque o JSON só aceita texto como chave.
        "eventos": {
            "1": {"id": 1, "nome": "Show de Rock Universitário", "data": "2026-12-05 20:00",
                  "local": "Auditório Central", "fileiras": 5, "assentos_por_fileira": 8},
            "2": {"id": 2, "nome": "Peça: O Auto da Compadecida", "data": "2026-12-12 19:00",
                  "local": "Teatro Municipal", "fileiras": 6, "assentos_por_fileira": 10},
            "3": {"id": 3, "nome": "Palestra: Carreira em Tecnologia", "data": "2027-03-20 14:00",
                  "local": "Sala 301-INF", "fileiras": 3, "assentos_por_fileira": 6},
            # Evento no passado, para demonstrar o erro "Evento já aconteceu".
            "4": {"id": 4, "nome": "Festival de Inverno", "data": "2026-07-10 18:00",
                  "local": "Praça Central", "fileiras": 2, "assentos_por_fileira": 5},
        },
        "ingressos": {},
    }


def carregar_dados():
    """Lê dados.json; se não existir, começa com os dados de exemplo."""
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    return dados_iniciais()


def salvar_dados():
    """Grava o dicionário inteiro em dados.json (sempre dentro da trava_dados)."""
    with trava_dados:
        with open(ARQUIVO_DADOS, "w", encoding="utf-8") as arquivo:
            # ensure_ascii=False mantém os acentos legíveis no arquivo.
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)


# Variável global com todos os dados do sistema.
dados = carregar_dados()


# =====================================================================
# PARTE 2 - FUNÇÕES AUXILIARES (regras usadas por várias funções da API)
# =====================================================================

def evento_ja_aconteceu(evento):
    """True se a data do evento já passou."""
    return datetime.strptime(evento["data"], FORMATO_DATA) < datetime.now()


def gerar_codigos_assentos(evento):
    """Gera a lista de assentos: fileira A, B, C... e números 1, 2, 3..."""
    codigos = []
    for f in range(evento["fileiras"]):
        letra = chr(ord("A") + f)                  # 0 -> "A", 1 -> "B"...
        for n in range(1, evento["assentos_por_fileira"] + 1):
            codigos.append(f"{letra}{n}")          # "A1", "A2"...
    return codigos


def assentos_vendidos(id_evento):
    """Conjunto de assentos ocupados (ingresso válido ou já usado)."""
    return {
        ing["assento"]
        for ing in dados["ingressos"].values()
        if ing["id_evento"] == id_evento and ing["status"] in ("valido", "usado")
    }


def evento_para_mensagem(evento):
    """Converte o dicionário Python na MENSAGEM Evento definida no .proto."""
    total = evento["fileiras"] * evento["assentos_por_fileira"]
    return ingressos_pb2.Evento(
        id=evento["id"],
        nome=evento["nome"],
        data=evento["data"],
        local=evento["local"],
        total_assentos=total,
        assentos_livres=total - len(assentos_vendidos(evento["id"])),
    )


def ingresso_para_mensagem(ingresso):
    """Converte o dicionário do ingresso na mensagem Ingresso do .proto."""
    evento = dados["eventos"][str(ingresso["id_evento"])]
    return ingressos_pb2.Ingresso(
        id=ingresso["id"],
        usuario=ingresso["usuario"],
        id_evento=ingresso["id_evento"],
        nome_evento=evento["nome"],
        data_evento=evento["data"],
        assento=ingresso["assento"],
        status=ingresso["status"],
        comprado_em=ingresso["comprado_em"],
    )


# =====================================================================
# PARTE 3 - A API REMOTA (o que o cliente pode chamar)
# =====================================================================
# A classe herda de VendaIngressosServicer, o "esqueleto" gerado pelo
# protoc. Para cada "rpc" do .proto escrevemos um método com o MESMO nome.
# Todo método recebe:
#   request -> a mensagem que veio do cliente (já convertida de bytes para objeto)
#   context -> informações da chamada (ex.: context.peer() = IP:porta do cliente)
# e devolve uma mensagem de resposta, que o gRPC converte em bytes e envia.

class VendaIngressos(ingressos_pb2_grpc.VendaIngressosServicer):

    # -----------------------------------------------------------------
    # listar_eventos()
    # -----------------------------------------------------------------
    def ListarEventos(self, request, context):
        # context.peer() mostra quem chamou, ex.: "ipv4:192.168.0.15:53422".
        # Repare que o cliente também usa uma porta (escolhida pelo sistema).
        print(f"[{context.peer()}] ListarEventos")
        with trava_dados:
            futuros = [evento_para_mensagem(e) for e in dados["eventos"].values()
                       if not evento_ja_aconteceu(e)]
        if not futuros:
            return ingressos_pb2.ListaEventos(sucesso=False, mensagem="Nenhum evento disponível")
        return ingressos_pb2.ListaEventos(sucesso=True, mensagem=f"{len(futuros)} evento(s)",
                                          eventos=futuros)

    # -----------------------------------------------------------------
    # consultar_assentos(id_evento)
    # -----------------------------------------------------------------
    def ConsultarAssentos(self, request, context):
        print(f"[{context.peer()}] ConsultarAssentos evento={request.id_evento}")
        with trava_dados:
            evento = dados["eventos"].get(str(request.id_evento))
            if evento is None:
                return ingressos_pb2.MapaAssentos(sucesso=False, mensagem="Evento não encontrado")
            vendidos = assentos_vendidos(evento["id"])
            mapa = [ingressos_pb2.Assento(codigo=c, vendido=(c in vendidos))
                    for c in gerar_codigos_assentos(evento)]
        return ingressos_pb2.MapaAssentos(
            sucesso=True, mensagem="OK", nome_evento=evento["nome"],
            fileiras=evento["fileiras"], assentos_por_fileira=evento["assentos_por_fileira"],
            assentos=mapa)

    # -----------------------------------------------------------------
    # comprar_ingresso(usuario, id_evento, assento)
    # A FUNÇÃO MAIS IMPORTANTE DA DEMONSTRAÇÃO (concorrência)
    # -----------------------------------------------------------------
    def ComprarIngresso(self, request, context):
        print(f"[{context.peer()}] ComprarIngresso {request.usuario} "
              f"evento={request.id_evento} assento={request.assento}")
        usuario = request.usuario.strip()
        assento = request.assento.strip().upper()     # aceita "a1" e vira "A1"

        if not usuario:
            return ingressos_pb2.RespostaIngresso(sucesso=False, mensagem="Usuário não informado")

        # trava_venda: a partir daqui, só UMA compra por vez passa (se ligada).
        with trava_venda:
            # PASSO 1: verificar (ler os dados)
            with trava_dados:
                evento = dados["eventos"].get(str(request.id_evento))
                if evento is None:
                    return ingressos_pb2.RespostaIngresso(sucesso=False, mensagem="Evento não encontrado")
                if evento_ja_aconteceu(evento):
                    return ingressos_pb2.RespostaIngresso(sucesso=False, mensagem="Evento já aconteceu")
                if assento not in gerar_codigos_assentos(evento):
                    return ingressos_pb2.RespostaIngresso(sucesso=False, mensagem="Assento inexistente")
                if assento in assentos_vendidos(evento["id"]):
                    return ingressos_pb2.RespostaIngresso(sucesso=False, mensagem="Assento já vendido")

            # PASSO 2: "processar o pagamento" (só uma espera, para simular).
            # SEM a trava_venda, várias threads chegam aqui ao mesmo tempo,
            # TODAS achando que o assento está livre... e todas vendem.
            # Isso é a "condição de corrida" (race condition) da aula de sincronização.
            time.sleep(TEMPO_PAGAMENTO)

            # PASSO 3: registrar a venda (escrever nos dados)
            with trava_dados:
                novo_id = dados["proximo_id_ingresso"]
                dados["proximo_id_ingresso"] += 1
                ingresso = {
                    "id": novo_id,
                    "usuario": usuario,
                    "id_evento": evento["id"],
                    "assento": assento,
                    "status": "valido",
                    "comprado_em": datetime.now().strftime(FORMATO_DATA),
                    # histórico de donos, útil para a transferência
                    "historico": [f"comprado por {usuario}"],
                }
                dados["ingressos"][str(novo_id)] = ingresso
                salvar_dados()
                resposta = ingresso_para_mensagem(ingresso)

        return ingressos_pb2.RespostaIngresso(sucesso=True,
                                              mensagem=f"Compra realizada! Ingresso nº {novo_id}",
                                              ingresso=resposta)

    # -----------------------------------------------------------------
    # cancelar_compra(usuario, id_ingresso)
    # -----------------------------------------------------------------
    def CancelarCompra(self, request, context):
        print(f"[{context.peer()}] CancelarCompra {request.usuario} ingresso={request.id_ingresso}")
        with trava_dados:
            ingresso = dados["ingressos"].get(str(request.id_ingresso))
            if ingresso is None:
                return ingressos_pb2.Resposta(sucesso=False, mensagem="Ingresso não encontrado")
            if ingresso["usuario"] != request.usuario.strip():
                return ingressos_pb2.Resposta(sucesso=False, mensagem="Não autorizado: o ingresso é de outro usuário")
            if ingresso["status"] == "cancelado":
                return ingressos_pb2.Resposta(sucesso=False, mensagem="Ingresso já estava cancelado")
            if ingresso["status"] == "usado":
                return ingressos_pb2.Resposta(sucesso=False, mensagem="Ingresso já usado na entrada")
            evento = dados["eventos"][str(ingresso["id_evento"])]
            if evento_ja_aconteceu(evento):
                return ingressos_pb2.Resposta(sucesso=False, mensagem="Evento já aconteceu")
            ingresso["status"] = "cancelado"            # o assento volta a ficar livre
            ingresso["historico"].append(f"cancelado por {ingresso['usuario']}")
            salvar_dados()
        return ingressos_pb2.Resposta(sucesso=True, mensagem="Compra cancelada e assento liberado")

    # -----------------------------------------------------------------
    # consultar_ingressos_usuario(usuario)
    # -----------------------------------------------------------------
    def ConsultarIngressosUsuario(self, request, context):
        print(f"[{context.peer()}] ConsultarIngressosUsuario {request.usuario}")
        with trava_dados:
            lista = [ingresso_para_mensagem(i) for i in dados["ingressos"].values()
                     if i["usuario"] == request.usuario.strip()]
        if not lista:
            return ingressos_pb2.ListaIngressos(sucesso=False,
                                                mensagem="Nenhum ingresso encontrado para o usuário")
        return ingressos_pb2.ListaIngressos(sucesso=True, mensagem=f"{len(lista)} ingresso(s)",
                                            ingressos=lista)

    # -----------------------------------------------------------------
    # consultar_ingresso(id_ingresso)
    # -----------------------------------------------------------------
    def ConsultarIngresso(self, request, context):
        print(f"[{context.peer()}] ConsultarIngresso {request.id_ingresso}")
        with trava_dados:
            ingresso = dados["ingressos"].get(str(request.id_ingresso))
            if ingresso is None:
                return ingressos_pb2.RespostaIngresso(sucesso=False, mensagem="Ingresso não encontrado")
            return ingressos_pb2.RespostaIngresso(sucesso=True, mensagem="OK",
                                                  ingresso=ingresso_para_mensagem(ingresso))

    # -----------------------------------------------------------------
    # EXTRA: criar_evento(nome, data, local, fileiras, assentos_por_fileira)
    # -----------------------------------------------------------------
    def CriarEvento(self, request, context):
        print(f"[{context.peer()}] CriarEvento {request.nome}")
        nome = request.nome.strip()
        if not nome or not request.local.strip():
            return ingressos_pb2.RespostaEvento(sucesso=False, mensagem="Nome e local são obrigatórios")
        try:
            data = datetime.strptime(request.data.strip(), FORMATO_DATA)
        except ValueError:
            return ingressos_pb2.RespostaEvento(sucesso=False,
                                                mensagem="Data inválida (use AAAA-MM-DD HH:MM)")
        if data < datetime.now():
            return ingressos_pb2.RespostaEvento(sucesso=False, mensagem="Data no passado")
        if not (1 <= request.fileiras <= 26) or not (1 <= request.assentos_por_fileira <= 50):
            return ingressos_pb2.RespostaEvento(sucesso=False,
                                                mensagem="Use de 1 a 26 fileiras e de 1 a 50 assentos por fileira")
        with trava_dados:
            for e in dados["eventos"].values():
                if e["nome"].lower() == nome.lower() and e["data"] == request.data.strip():
                    return ingressos_pb2.RespostaEvento(sucesso=False, mensagem="Evento já existe")
            novo_id = dados["proximo_id_evento"]
            dados["proximo_id_evento"] += 1
            evento = {"id": novo_id, "nome": nome, "data": request.data.strip(),
                      "local": request.local.strip(), "fileiras": request.fileiras,
                      "assentos_por_fileira": request.assentos_por_fileira}
            dados["eventos"][str(novo_id)] = evento
            salvar_dados()
            mensagem_evento = evento_para_mensagem(evento)
        return ingressos_pb2.RespostaEvento(sucesso=True, mensagem=f"Evento criado com id {novo_id}",
                                            evento=mensagem_evento)

    # -----------------------------------------------------------------
    # EXTRA: transferir_ingresso(usuario_origem, usuario_destino, id_ingresso)
    # -----------------------------------------------------------------
    def TransferirIngresso(self, request, context):
        print(f"[{context.peer()}] TransferirIngresso {request.id_ingresso} "
              f"{request.usuario_origem} -> {request.usuario_destino}")
        origem = request.usuario_origem.strip()
        destino = request.usuario_destino.strip()
        if not destino or destino == origem:
            return ingressos_pb2.Resposta(sucesso=False, mensagem="Usuário destino inválido")
        with trava_dados:
            ingresso = dados["ingressos"].get(str(request.id_ingresso))
            if ingresso is None:
                return ingressos_pb2.Resposta(sucesso=False, mensagem="Ingresso não encontrado")
            if ingresso["usuario"] != origem:
                return ingressos_pb2.Resposta(sucesso=False, mensagem="Não autorizado: o ingresso é de outro usuário")
            if ingresso["status"] != "valido":
                return ingressos_pb2.Resposta(sucesso=False, mensagem=f"Ingresso {ingresso['status']}, não pode ser transferido")
            ingresso["usuario"] = destino
            ingresso["historico"].append(f"transferido de {origem} para {destino}")
            salvar_dados()
        return ingressos_pb2.Resposta(sucesso=True, mensagem=f"Ingresso transferido para {destino}")

    # -----------------------------------------------------------------
    # EXTRA: validar_entrada(id_ingresso)  (check-in na portaria)
    # -----------------------------------------------------------------
    def ValidarEntrada(self, request, context):
        print(f"[{context.peer()}] ValidarEntrada {request.id_ingresso}")
        with trava_dados:
            ingresso = dados["ingressos"].get(str(request.id_ingresso))
            if ingresso is None:
                return ingressos_pb2.RespostaIngresso(sucesso=False, mensagem="Ingresso não encontrado")
            if ingresso["status"] == "usado":
                return ingressos_pb2.RespostaIngresso(sucesso=False, mensagem="Ingresso já usado",
                                                      ingresso=ingresso_para_mensagem(ingresso))
            if ingresso["status"] == "cancelado":
                return ingressos_pb2.RespostaIngresso(sucesso=False, mensagem="Ingresso cancelado",
                                                      ingresso=ingresso_para_mensagem(ingresso))
            ingresso["status"] = "usado"
            ingresso["historico"].append("entrada validada na portaria")
            salvar_dados()
            return ingressos_pb2.RespostaIngresso(sucesso=True, mensagem="Entrada liberada!",
                                                  ingresso=ingresso_para_mensagem(ingresso))

    # -----------------------------------------------------------------
    # EXTRA: relatorio_vendas(id_evento)
    # -----------------------------------------------------------------
    def RelatorioVendas(self, request, context):
        print(f"[{context.peer()}] RelatorioVendas evento={request.id_evento}")
        with trava_dados:
            evento = dados["eventos"].get(str(request.id_evento))
            if evento is None:
                return ingressos_pb2.Relatorio(sucesso=False, mensagem="Evento não encontrado")
            do_evento = [i for i in dados["ingressos"].values() if i["id_evento"] == evento["id"]]
            total = evento["fileiras"] * evento["assentos_por_fileira"]
            # Contamos ingressos (e não assentos): assim, se houver venda dupla
            # no modo --sem-trava, o relatório denuncia (vendidos > assentos únicos).
            vendidos = sum(1 for i in do_evento if i["status"] in ("valido", "usado"))
            usados = sum(1 for i in do_evento if i["status"] == "usado")
            cancelados = sum(1 for i in do_evento if i["status"] == "cancelado")
        return ingressos_pb2.Relatorio(
            sucesso=True, mensagem="OK", nome_evento=evento["nome"], total_assentos=total,
            vendidos=vendidos, livres=total - vendidos, ocupacao=100.0 * vendidos / total,
            usados=usados, cancelados=cancelados)


# =====================================================================
# PARTE 4 - LIGANDO O SERVIDOR NA REDE
# =====================================================================

def descobrir_ip_local():
    """Descobre o IP desta máquina na rede local (só para mostrar na tela).

    Truque: criamos um socket UDP e "conectamos" a um IP externo. Como UDP
    não tem handshake, NENHUM pacote é enviado; o sistema operacional só
    escolhe por qual placa de rede sairia, e assim sabemos o nosso IP.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"   # sem rede: só funciona na própria máquina
    finally:
        s.close()


def iniciar():
    # 1) Cria o servidor gRPC com um "pool" de 10 threads.
    #    Cada chamada que chega é entregue a uma thread livre, por isso
    #    10 clientes podem ser atendidos ao mesmo tempo (e por isso
    #    precisamos das travas lá em cima).
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # 2) Registra a nossa classe: "quando chegar uma chamada para o serviço
    #    VendaIngressos, entregue para este objeto". É aqui que o stub do
    #    servidor fica ligado às nossas funções.
    ingressos_pb2_grpc.add_VendaIngressosServicer_to_server(VendaIngressos(), servidor)

    # 3) Diz em qual IP e porta escutar.
    #    "0.0.0.0" = aceitar conexões vindas de QUALQUER placa de rede
    #    (Wi-Fi, cabo...). Se fosse "127.0.0.1", só a própria máquina
    #    conseguiria conectar, e o PC do laboratório seria recusado.
    #    "insecure" = sem criptografia (TLS). Os dados viajam legíveis,
    #    o que é ótimo para estudar no Wireshark, mas não para produção.
    servidor.add_insecure_port(f"0.0.0.0:{PORTA}")

    # 4) Liga o servidor. Por baixo dos panos, o gRPC cria um socket TCP,
    #    faz bind (reserva a porta) e listen (fica esperando conexões).
    servidor.start()

    salvar_dados()   # cria o dados.json na primeira execução
    ip = descobrir_ip_local()
    print("=" * 62)
    print(" Servidor de ingressos (gRPC) no ar!")
    print(f" Escutando na porta {PORTA}")
    print(f" Nesta máquina:      python cliente.py localhost")
    print(f" Em outra máquina:   python cliente.py {ip}")
    if USAR_TRAVA_VENDA:
        print(" Trava de venda: LIGADA (modo correto)")
    else:
        print(" Trava de venda: DESLIGADA (modo demonstração, pode vender em dobro!)")
    print(" Ctrl+C para desligar")
    print("=" * 62)

    # 5) Mantém o programa vivo esperando chamadas (senão ele terminaria aqui).
    try:
        servidor.wait_for_termination()
    except KeyboardInterrupt:
        print("\nDesligando o servidor...")
        servidor.stop(grace=1)   # dá 1 segundo para terminar chamadas em andamento


# Só inicia se este arquivo for executado diretamente (python servidor.py).
if __name__ == "__main__":
    iniciar()
