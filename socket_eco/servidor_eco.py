# =====================================================================
# servidor_eco.py  -  SOCKET "PURO": a base que o gRPC esconde de você
# =====================================================================
# Um servidor de ECO: devolve em MAIÚSCULAS tudo o que o cliente mandar.
# Aqui fazemos À MÃO tudo o que o gRPC faz sozinho no servidor.py.
# Rode:  python servidor_eco.py      e depois o cliente_eco.py
# =====================================================================

import socket   # a biblioteca de sockets do sistema operacional

PORTA = 5000

# 1) Cria o socket.
#    AF_INET     = vamos usar endereços IPv4 (ex.: 192.168.0.15)
#    SOCK_STREAM = vamos usar TCP (conexão confiável, em ordem, sem perdas)
#    (se fosse SOCK_DGRAM, seria UDP)
servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Permite reaproveitar a porta logo após fechar o programa
# (sem isso, às vezes o sistema segura a porta por alguns segundos).
servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# 2) BIND: reserva a porta 5000 para ESTE programa.
#    "0.0.0.0" = aceita conexões vindas de qualquer placa de rede.
servidor.bind(("0.0.0.0", PORTA))

# 3) LISTEN: começa a escutar. O 1 é o tamanho da fila de espera.
servidor.listen(1)
print(f"Servidor de eco esperando na porta {PORTA}...")

while True:
    # 4) ACCEPT: fica PARADO aqui até um cliente conectar.
    #    Nesse momento já aconteceu o "aperto de mão" do TCP (3-way handshake:
    #    SYN -> SYN/ACK -> ACK). Recebemos um NOVO socket só para esse cliente.
    conexao, endereco_cliente = servidor.accept()
    print(f"Cliente conectado: {endereco_cliente}")   # (ip, porta) do cliente

    # 5) RECV: lê até 1024 bytes que chegaram. Na rede só trafegam BYTES,
    #    então precisamos decodificar (bytes -> texto) com .decode().
    dados = conexao.recv(1024)
    mensagem = dados.decode("utf-8")
    print(f"Recebi: {mensagem}")

    # 6) SENDALL: envia a resposta, convertendo texto -> bytes com .encode().
    #    Esse "converter para bytes e de volta" é o MARSHALLING que, no gRPC,
    #    o Protobuf faz para você com mensagens bem mais complexas.
    conexao.sendall(mensagem.upper().encode("utf-8"))

    # 7) CLOSE: encerra a conexão com este cliente (TCP envia FIN).
    conexao.close()
