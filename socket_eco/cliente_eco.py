# =====================================================================
# cliente_eco.py  -  O CLIENTE DO SOCKET "PURO"
# =====================================================================
# Rode:  python cliente_eco.py               (servidor nesta máquina)
#        python cliente_eco.py 192.168.0.15  (servidor em outra máquina)
# =====================================================================

import socket
import sys

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"   # 127.0.0.1 = "eu mesmo"
PORTA = 5000

# 1) Cria um socket TCP, igual ao do servidor.
cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# 2) CONNECT: liga para o servidor (IP + porta). Aqui acontece o handshake TCP.
#    Repare: o cliente NÃO escolhe a própria porta; o sistema operacional
#    sorteia uma porta livre (porta "efêmera", ex.: 53422).
cliente.connect((host, PORTA))

texto = input("Digite uma mensagem: ")

# 3) Envia o texto como bytes.
cliente.sendall(texto.encode("utf-8"))

# 4) Espera a resposta e converte bytes -> texto.
resposta = cliente.recv(1024).decode("utf-8")
print(f"Servidor respondeu: {resposta}")

# 5) Fecha a conexão.
cliente.close()

# PERCEBA O QUE FALTOU AQUI E O gRPC RESOLVE PARA VOCÊ:
#  - Não existe "função": só mandamos bytes. Para ter várias operações
#    (comprar, cancelar...), teríamos que inventar um protocolo próprio
#    ("COMPRAR;joao;1;A1") e escrever o código que separa as partes.
#  - Mensagens grandes podem chegar em pedaços; teríamos que juntar.
#  - Não há tipos (int, string, lista); tudo vira texto na mão.
#  O gRPC + Protobuf fazem tudo isso, gerando o código a partir do .proto.
