# =====================================================================
# teste_concorrencia.py  -  DEMONSTRAÇÃO: 10 PESSOAS, 1 ASSENTO
# =====================================================================
# Simula 10 clientes diferentes tentando comprar o MESMO assento (A1)
# no MESMO instante. O resultado correto é: 1 compra aprovada e
# 9 recusadas com "Assento já vendido".
#
# Roteiro para a apresentação:
#   1) python servidor.py --sem-trava   e depois   python teste_concorrencia.py
#      -> várias pessoas "compram" o mesmo assento (venda duplicada!)
#   2) Ctrl+C no servidor, rode   python servidor.py   e repita o teste
#      -> só 1 compra passa
#
# Como rodar:
#   python teste_concorrencia.py                 (servidor nesta máquina)
#   python teste_concorrencia.py 192.168.0.15    (servidor em outra máquina)
# =====================================================================

import sys
import threading            # cada "pessoa" será uma thread
from datetime import datetime, timedelta

import grpc
import ingressos_pb2
import ingressos_pb2_grpc

PORTA = 50051
PESSOAS = 10
ASSENTO = "A1"

host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
endereco = f"{host}:{PORTA}"

# ---------------------------------------------------------------------
# 1) Cria um evento NOVO só para o teste (assim o A1 começa livre).
# ---------------------------------------------------------------------
canal_admin = grpc.insecure_channel(endereco)
admin = ingressos_pb2_grpc.VendaIngressosStub(canal_admin)

agora = datetime.now()
pedido_evento = ingressos_pb2.PedidoCriarEvento(
    nome=f"Teste de concorrência {agora:%H:%M:%S}",
    data=(agora + timedelta(days=30)).strftime("%Y-%m-%d %H:%M"),
    local="Laboratório",
    fileiras=2,
    assentos_por_fileira=5,
)
try:
    resposta_evento = admin.CriarEvento(pedido_evento, timeout=5)
except grpc.RpcError as erro:
    print(f"Não consegui falar com o servidor em {endereco}: {erro.code().name}")
    sys.exit(1)
id_evento = resposta_evento.evento.id
print(f"Evento de teste criado (id {id_evento}). {PESSOAS} pessoas vão tentar comprar o {ASSENTO}...\n")

# ---------------------------------------------------------------------
# 2) A "largada": uma Barreira faz todas as threads esperarem até que as
#    10 estejam prontas, e então todas disparam juntas.
# ---------------------------------------------------------------------
largada = threading.Barrier(PESSOAS)
resultados = []                 # lista compartilhada com o resultado de cada pessoa
trava_resultados = threading.Lock()   # protege a lista acima (ironia: também precisamos de trava aqui!)


def pessoa(numero):
    # Cada pessoa abre o SEU próprio canal = sua própria conexão TCP,
    # como 10 celulares diferentes acessando o sistema.
    # Detalhe: por padrão o gRPC REAPROVEITA a mesma conexão TCP para canais
    # que apontam para o mesmo endereço (economia). A opção abaixo desliga
    # esse reaproveitamento, para cada pessoa ter a sua conexão de verdade.
    # No log do servidor dá para ver: cada pessoa chega por uma porta diferente.
    canal = grpc.insecure_channel(endereco, options=[("grpc.use_local_subchannel_pool", 1)])
    stub = ingressos_pb2_grpc.VendaIngressosStub(canal)
    pedido = ingressos_pb2.PedidoCompra(usuario=f"pessoa{numero:02d}",
                                        id_evento=id_evento, assento=ASSENTO)
    largada.wait()                                   # espera todo mundo ficar pronto...
    resposta = stub.ComprarIngresso(pedido, timeout=10)   # ...e todos compram juntos!
    with trava_resultados:
        resultados.append((numero, resposta.sucesso, resposta.mensagem))
    canal.close()


threads = [threading.Thread(target=pessoa, args=(n,)) for n in range(1, PESSOAS + 1)]
for t in threads:
    t.start()
for t in threads:
    t.join()      # espera todas as threads terminarem

# ---------------------------------------------------------------------
# 3) Mostra o resultado.
# ---------------------------------------------------------------------
for numero, sucesso, mensagem in sorted(resultados):
    print(f"  pessoa{numero:02d}: {'APROVADA ' if sucesso else 'recusada '} {mensagem}")

aprovadas = sum(1 for _, sucesso, _ in resultados if sucesso)
relatorio = admin.RelatorioVendas(ingressos_pb2.PedidoEvento(id_evento=id_evento), timeout=5)
print(f"\nCompras aprovadas para o assento {ASSENTO}: {aprovadas}")
print(f"Ingressos emitidos no relatório do evento: {relatorio.vendidos}")
if aprovadas == 1:
    print("CORRETO: só uma pessoa ficou com o assento. A trava funcionou.")
else:
    print(f"PROBLEMA: {aprovadas} pessoas pagaram pelo MESMO assento! (condição de corrida)")
canal_admin.close()
