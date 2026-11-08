# Sistema de Venda de Ingressos com gRPC

Trabalho da disciplina **Sistemas Distribuídos (IM873 – DCC/IM/UFRRJ)**: uma aplicação distribuída cliente/servidor usando **RPC (Remote Procedure Call)**.

O servidor guarda eventos e ingressos e oferece uma API remota com 10 funções: listar eventos, ver o mapa de assentos, comprar, cancelar, consultar ingressos, criar evento, transferir, validar a entrada na portaria e gerar relatório. O cliente é um menu de texto que pode rodar em outra máquina (por exemplo, servidor no Windows e cliente no Linux) e chama essas funções como se fossem locais.

O destaque do projeto é o **controle de concorrência**: quando várias pessoas tentam comprar o mesmo assento ao mesmo tempo, apenas uma consegue. O script `teste_concorrencia.py` demonstra o problema (venda duplicada) e a solução (trava/lock).

**Tecnologias:** Python 3.10+ (versões mais antigas funcionam gerando os stubs de novo), gRPC (`grpcio`), Protocol Buffers (`grpcio-tools`), JSON para armazenamento.

---

## Estrutura do projeto

| Arquivo | Para que serve |
| --- | --- |
| `ingressos.proto` | O contrato da API: funções e mensagens. Cliente e servidor são gerados a partir dele |
| `ingressos_pb2.py`, `ingressos_pb2_grpc.py` | Código **gerado** pelo `protoc` (mensagens e stubs). Não editar à mão |
| `servidor.py` | Implementa as 10 funções, guarda os dados e escuta na porta 50051 |
| `cliente.py` | Menu de texto que chama as funções remotas |
| `teste_concorrencia.py` | 10 clientes tentando comprar o mesmo assento ao mesmo tempo |
| `socket_eco/` | Exemplo com socket TCP "puro", para comparar com o que o gRPC faz por nós |
| `dados.json` | Criado pelo servidor na primeira execução; guarda eventos e ingressos |
| `docs/` | Material de estudo: conceitos, instalação e roteiro da apresentação |

---

## Como executar (resumo)

O passo a passo completo, inclusive Windows, WSL, laboratório Linux, firewall e Wireshark, está em [docs/02_instalacao_e_execucao.md](docs/02_instalacao_e_execucao.md).

```bash
pip install -r requirements.txt
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ingressos.proto

python servidor.py                 # terminal 1 (máquina servidora)
python cliente.py                  # terminal 2, mesma máquina
python cliente.py 192.168.0.15     # ou em outra máquina, usando o IP do servidor
python teste_concorrencia.py       # demonstração de concorrência
```

Para a demonstração da condição de corrida, inicie o servidor com `python servidor.py --sem-trava`.

---

## Descrição da API

Todas as funções devolvem `sucesso` (verdadeiro/falso) e `mensagem` (texto explicando o resultado ou o erro), seguindo o padrão do enunciado: *"Retorno: sucesso ou mensagem de erro"*.

No gRPC os nomes das funções seguem o padrão `CamelCase`. A tabela mostra o nome no estilo do enunciado e o nome real no `.proto`.

### Funções principais

| Função (estilo do enunciado) | Nome no gRPC | Parâmetros | Retorno em caso de sucesso | Erros possíveis |
| --- | --- | --- | --- | --- |
| `listar_eventos()` | `ListarEventos` | nenhum | Lista de eventos futuros: id, nome, data, local, assentos livres e total | "Nenhum evento disponível" |
| `consultar_assentos(id_evento)` | `ConsultarAssentos` | id do evento | Mapa com cada assento (A1, A2...) e se está vendido | "Evento não encontrado" |
| `comprar_ingresso(usuario, id_evento, assento)` | `ComprarIngresso` | usuário, id do evento, código do assento | Ingresso emitido (número, evento, assento, status) | "Assento já vendido", "Evento não encontrado", "Evento já aconteceu", "Assento inexistente", "Usuário não informado" |
| `cancelar_compra(usuario, id_ingresso)` | `CancelarCompra` | usuário, número do ingresso | Confirmação; o assento volta a ficar livre | "Ingresso não encontrado", "Não autorizado", "Ingresso já estava cancelado", "Ingresso já usado na entrada", "Evento já aconteceu" |
| `consultar_ingressos_usuario(usuario)` | `ConsultarIngressosUsuario` | usuário | Lista de ingressos com evento, assento e status | "Nenhum ingresso encontrado para o usuário" |
| `consultar_ingresso(id_ingresso)` | `ConsultarIngresso` | número do ingresso | Dono, evento, assento, status e data da compra | "Ingresso não encontrado" |

### Funções extras

| Função (estilo do enunciado) | Nome no gRPC | Parâmetros | Retorno em caso de sucesso | Erros possíveis |
| --- | --- | --- | --- | --- |
| `criar_evento(nome, data, local, fileiras, assentos_por_fileira)` | `CriarEvento` | nome, data `AAAA-MM-DD HH:MM`, local, fileiras (1–26), assentos por fileira (1–50) | Evento criado com seu id | "Data inválida", "Data no passado", "Evento já existe", "Nome e local são obrigatórios" |
| `transferir_ingresso(usuario_origem, usuario_destino, id_ingresso)` | `TransferirIngresso` | dono atual, novo dono, número do ingresso | Confirmação da transferência | "Ingresso não encontrado", "Não autorizado", "Usuário destino inválido", "Ingresso usado/cancelado, não pode ser transferido" |
| `validar_entrada(id_ingresso)` | `ValidarEntrada` | número do ingresso | "Entrada liberada!" e o ingresso passa a "usado" | "Ingresso já usado", "Ingresso cancelado", "Ingresso não encontrado" |
| `relatorio_vendas(id_evento)` | `RelatorioVendas` | id do evento | Total de assentos, vendidos, livres, % de ocupação, quantos já entraram e cancelados | "Evento não encontrado" |

**Status de um ingresso:** `valido` (comprado, ainda não usado) → `usado` (passou na portaria) ou `cancelado` (assento liberado).

---

## Exemplos de uso

### Pelo menu do cliente

```text
Seu nome de usuário: yago

Opção: 1
  [1] Show de Rock Universitário | 2026-12-05 20:00 | Auditório Central | 40/40 livres
  [2] Peça: O Auto da Compadecida | 2026-12-12 19:00 | Teatro Municipal | 60/60 livres

Opção: 3
  ID do evento: 1
  Assento (ex.: B4): b4
  Compra realizada! Ingresso nº 1

Opção: 2
  ID do evento: 1
  Show de Rock Universitário   ([  ] livre   [XX] vendido)
        1    2    3    4    5    6    7    8
  A   [  ] [  ] [  ] [  ] [  ] [  ] [  ] [  ]
  B   [  ] [  ] [  ] [XX] [  ] [  ] [  ] [  ]

Opção: 3            (outra pessoa tentando o mesmo assento)
  Assento já vendido

Opção: 9            (portaria)
  Nº do ingresso: 1
  Entrada liberada!
```

### Chamando a API direto pelo código (o que o cliente faz por dentro)

```python
import grpc, ingressos_pb2, ingressos_pb2_grpc

canal = grpc.insecure_channel("192.168.0.15:50051")      # IP e porta do servidor
stub = ingressos_pb2_grpc.VendaIngressosStub(canal)        # o "dublê" do servidor

pedido = ingressos_pb2.PedidoCompra(usuario="yago", id_evento=1, assento="B4")
resposta = stub.ComprarIngresso(pedido, timeout=5)         # parece local, roda no servidor
print(resposta.sucesso, resposta.mensagem)                 # True  Compra realizada! Ingresso nº 1
```

### Demonstração de concorrência

```text
$ python servidor.py --sem-trava        $ python servidor.py
$ python teste_concorrencia.py          $ python teste_concorrencia.py
Compras aprovadas para o assento A1: 10  Compras aprovadas para o assento A1: 1
PROBLEMA: 10 pessoas pagaram pelo         CORRETO: só uma pessoa ficou com o
MESMO assento! (condição de corrida)      assento. A trava funcionou.
```

---

## Justificativas das escolhas de implementação

**Por que gRPC (e não socket puro, XML-RPC ou Java RMI)?**
- Com socket puro, teríamos que inventar um protocolo de mensagens e converter tudo à mão (veja `socket_eco/`). O RPC esconde isso e permite chamar funções remotas como se fossem locais, que é a ideia de transparência estudada na disciplina.
- O gRPC gera o stub do cliente e o esqueleto do servidor automaticamente a partir de um contrato (`.proto`), exatamente o papel dos stubs descritos na teoria de RPC.
- Ele é independente de linguagem e sistema operacional: o mesmo `.proto` funciona com servidor no Windows e cliente no Linux.
- É a tecnologia de RPC mais usada atualmente no mercado (Google, Netflix, Kubernetes). XML-RPC seria mais simples, mas é antigo e envia XML, que é bem maior. Java RMI só funciona entre programas Java.

**Por que Protocol Buffers?** É o formato de serialização (marshalling) do gRPC. As mensagens são binárias e compactas: o pedido de compra de exemplo ocupa 12 bytes em Protobuf, contra 52 bytes no equivalente em JSON. Os tipos (inteiro, texto, lista) ficam definidos no contrato, então cliente e servidor nunca discordam sobre o formato.

**Por que HTTP/2 e TCP?** É o transporte que o gRPC usa. O TCP garante que os bytes chegam completos e em ordem, o que é essencial numa compra (não pode chegar "meio pedido"). O HTTP/2 permite várias chamadas simultâneas na mesma conexão.

**Por que dicionário em memória + arquivo JSON?** O enunciado pede armazenamento simples. A memória deixa as consultas rápidas e o JSON garante que os dados sobrevivem quando o servidor é desligado, além de ser legível para conferir na apresentação. Um banco de dados seria o próximo passo num sistema real.

**Por que threads e travas (locks)?** O servidor atende até 10 clientes ao mesmo tempo, cada um numa thread. Como as threads compartilham os mesmos dados, usamos duas travas:
- `trava_dados`: impede que duas threads alterem o dicionário ou o arquivo ao mesmo tempo.
- `trava_venda`: torna "verificar se o assento está livre" e "registrar a venda" uma operação única (atômica). Sem ela, várias threads verificam ao mesmo tempo, todas veem o assento livre e todas vendem. É a condição de corrida estudada em sincronização, demonstrada com `--sem-trava`.

**Por que erros como `sucesso` + `mensagem` (e não códigos de erro do gRPC)?** Segue o formato de retorno do enunciado e deixa o cliente simples. Os códigos de erro do gRPC (`UNAVAILABLE`, `DEADLINE_EXCEEDED`) são usados só para falhas de **rede**, tratadas no cliente.

**Por que timeout nas chamadas?** Numa chamada remota o servidor pode cair ou a rede falhar. Com `timeout=5`, o cliente não fica travado para sempre e mostra uma mensagem clara (tolerância a falhas).

**Por que a porta 50051 e o endereço 0.0.0.0?** 50051 é a porta usada nos exemplos oficiais do gRPC e não exige administrador. Escutar em `0.0.0.0` aceita conexões de qualquer placa de rede; com `127.0.0.1`, só a própria máquina conseguiria conectar.

---

## Limitações conhecidas e melhorias futuras

- **Sem criptografia:** o canal é `insecure` (sem TLS), então os dados viajam legíveis na rede, o que dá para ver no Wireshark. Em produção usaríamos `grpc.secure_channel` com certificados.
- **Sem autenticação:** o usuário é só um nome digitado. Um sistema real exigiria login (por exemplo, tokens).
- **Servidor único:** se ele cair, o sistema para (ponto único de falha). A solução seria replicar o servidor, assunto das aulas de replicação e tolerância a falhas.
- **Reserva temporária:** sites reais seguram o assento por alguns minutos enquanto a pessoa paga. Ficou como melhoria futura.

---

**Autor:** Yago Samara · UFRRJ · 2026
