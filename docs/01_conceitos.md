# 1. Conceitos de rede e RPC, sem complicação

Este guia explica os termos que aparecem no código e na apresentação. Para cada um há uma analogia e onde ele aparece no projeto.

A analogia geral: pense na rede como os **Correios**.

---

## Glossário

| Termo | Explicação simples | Onde aparece no projeto |
| --- | --- | --- |
| **Endereço IP** | O endereço do **prédio** (computador) na rede. Ex.: `192.168.0.15`. | O IP que você passa para o `cliente.py` |
| **Porta** | O número do **apartamento** dentro do prédio. É um número de **software** (0 a 65535) que o sistema operacional usa para saber **qual programa** recebe os dados. Não é algo físico: a porta 80 ser de sites é só uma convenção. | `PORTA = 50051` no servidor e no cliente |
| **Porta efêmera** | A porta "de retorno" do cliente, sorteada pelo sistema a cada conexão (ex.: 53422). | Aparece no log do servidor: `[ipv4:192.168.0.20:53422]` |
| **localhost / 127.0.0.1** | "Eu mesmo". Um endereço que sempre aponta para a própria máquina, sem passar pela rede de verdade. | `python cliente.py` sem IP |
| **0.0.0.0** | No servidor, significa "aceito conexões chegando por **qualquer** placa de rede" (Wi-Fi, cabo...). | `add_insecure_port("0.0.0.0:50051")` |
| **Socket** | A **tomada** que o programa usa para falar com a rede. É uma ponta da conversa, identificada por IP + porta. Toda comunicação de rede passa por um socket, inclusive a do gRPC. | `socket_eco/` mostra um na mão |
| **TCP** | Entrega **confiável**: abre uma conexão antes, numera os pedaços, confirma o recebimento (ACK), reenvia o que se perdeu e entrega **na ordem**. Como uma carta registrada com aviso de recebimento. | O gRPC roda sobre TCP |
| **UDP** | Entrega **sem garantia**: não abre conexão, não confirma, não reenvia, não ordena. É mais rápido, por isso é usado em vídeo ao vivo, jogos e DNS, onde chegar rápido importa mais que chegar tudo. Como jogar panfleto na caixa de correio. | Só no truque que descobre o IP do servidor |
| **Confiável ≠ seguro** | O TCP garante que chega, mas **não** esconde o conteúdo. Quem esconde (criptografa) é outra camada, o **TLS** (o "s" do https). | Nosso canal é `insecure`: dá para ler no Wireshark |
| **Handshake (aperto de mão)** | Os 3 pacotes que abrem uma conexão TCP: `SYN` ("quer conversar?") → `SYN-ACK` ("quero, e você?") → `ACK` ("combinado"). | Primeiros pacotes no Wireshark |
| **Cliente / servidor** | O servidor fica **esperando** pedidos numa porta conhecida; o cliente **toma a iniciativa** de se conectar. | `servidor.py` e `cliente.py` |
| **Firewall** | O porteiro da máquina: decide quais conexões de fora podem entrar. O do Windows bloqueia por padrão. | Liberar a porta 50051 no Windows |
| **RPC** | Chamar uma função que roda em **outro computador** como se fosse local. O programador escreve `stub.ComprarIngresso(...)` e não precisa pensar em sockets nem bytes. | Todo o projeto |
| **Stub** | O **dublê** do servidor dentro do cliente. Ele tem as mesmas funções, mas em vez de executá-las, empacota o pedido, envia pela rede e devolve a resposta. No servidor existe o par dele, que desempacota e chama a função de verdade. | `ingressos_pb2_grpc.py` (gerado) |
| **Marshalling / serialização** | Transformar dados (objetos, números, textos) em **bytes** para viajar pela rede. O caminho inverso é unmarshalling / desserialização. | Feito pelo Protobuf |
| **Protobuf** | O formato de serialização do gRPC. Binário e compacto: o nosso pedido de compra vira **12 bytes** (em JSON seriam 52). | `ingressos.proto` |
| **IDL / contrato** | Arquivo que descreve as funções e os dados, independente de linguagem. No gRPC é o `.proto`. | `ingressos.proto` |
| **HTTP/2** | Versão moderna do protocolo da web. O gRPC usa para levar as chamadas, porque permite várias chamadas ao mesmo tempo numa só conexão TCP. | Visível no Wireshark |
| **gRPC** | Framework de RPC criado pelo Google: junta Protobuf (formato) + HTTP/2 (transporte) + geração automática de stubs. | Todo o projeto |
| **Thread** | Uma "linha de execução" dentro do programa. O servidor tem 10, então atende 10 clientes ao mesmo tempo. Todas enxergam a mesma memória. | `ThreadPoolExecutor(max_workers=10)` |
| **Condição de corrida** | Erro que acontece quando duas threads leem e escrevem o mesmo dado ao mesmo tempo, e o resultado depende de "quem chega primeiro". | Venda duplicada com `--sem-trava` |
| **Lock (trava)** | Um cadeado: só a thread que pegou o cadeado entra naquele trecho; as outras esperam na fila. | `trava_venda` e `trava_dados` |
| **Timeout / deadline** | Tempo máximo que o cliente espera uma resposta antes de desistir. Numa chamada local isso não existe; numa remota é essencial. | `timeout=5` no cliente |

---

## Por debaixo dos panos: a viagem de uma compra

Você está no PC Linux do laboratório (`192.168.0.20`) e compra o assento B4. O servidor está no seu notebook Windows (`192.168.0.15`).

**No cliente (Linux):**

1. O `cliente.py` monta a mensagem `PedidoCompra(usuario="yago", id_evento=1, assento="B4")` e chama `stub.ComprarIngresso(pedido, timeout=5)`. Para o programador, acabou: parece uma função comum.
2. **Marshalling.** O stub entrega a mensagem ao Protobuf, que a transforma nestes 12 bytes:

   ```text
   0a 04 79 61 67 6f   10 01   1a 02 42 34
   │  │  y  a  g  o    │  │    │  │  B  4
   │  └ tamanho 4      │  └ 1  │  └ tamanho 2
   └ campo 1 (texto)   └ campo 2 (número)  └ campo 3 (texto)
   ```

   Repare que vão os **números dos campos** do `.proto` (1, 2, 3), e não os nomes. Por isso fica tão pequeno.
3. **HTTP/2.** O gRPC monta um pedido HTTP/2 `POST` para o caminho `/ingressos.VendaIngressos/ComprarIngresso`, com cabeçalho `content-type: application/grpc`. Os 12 bytes vão no corpo, com 5 bytes na frente (1 diz se está comprimido, 4 dizem o tamanho).
4. **TCP.** Se ainda não há conexão com `192.168.0.15:50051`, o sistema faz o handshake (SYN, SYN-ACK, ACK). O sistema também sorteia uma porta efêmera para o cliente, por exemplo 53422. Depois o TCP envia os dados em **segmentos** numerados e espera os ACKs.
5. **IP.** Cada segmento ganha um envelope com IP de origem `192.168.0.20` e destino `192.168.0.15`. A rede (switch, roteador) entrega o pacote ao notebook.

**No servidor (Windows):**

6. O **firewall** do Windows confere se a porta 50051 pode receber conexões de fora. Se não puder, o pacote é descartado e o cliente recebe `UNAVAILABLE` ou estoura o timeout.
7. O sistema operacional olha a porta de destino (50051) e entrega os bytes ao **socket** do processo Python que fez `bind` nela.
8. A biblioteca gRPC lê o HTTP/2, vê o caminho `/ingressos.VendaIngressos/ComprarIngresso` e sabe qual função chamar. Faz o **unmarshalling** (bytes → objeto `PedidoCompra`).
9. Uma **thread** livre do pool executa `VendaIngressos.ComprarIngresso(request, context)`, a função que **nós** escrevemos. Ela pega a trava, verifica o assento, "processa o pagamento", registra e salva no `dados.json`.

**A volta:**

10. A função devolve um `RespostaIngresso`. O gRPC serializa, envia de volta pela mesma conexão TCP e o stub do cliente desserializa. A linha `resposta = stub.ComprarIngresso(...)` finalmente "retorna", e o menu mostra "Compra realizada!".

Tudo isso leva poucos milissegundos numa rede local.

---

## Socket puro x gRPC

| Tarefa | Com socket puro (`socket_eco/`) | Com gRPC |
| --- | --- | --- |
| Abrir conexão, bind, listen, accept | Você escreve | Automático (`grpc.server`, `insecure_channel`) |
| Definir as operações | Inventar um protocolo, ex.: `"COMPRAR;yago;1;B4"` | Declarar `rpc ComprarIngresso` no `.proto` |
| Converter dados em bytes | `.encode()` / `.decode()` e separar por `;` à mão | Protobuf, com tipos |
| Mensagens grandes chegando em pedaços | Juntar os pedaços você mesmo | Automático |
| Vários clientes ao mesmo tempo | Criar threads você mesmo | Pool de threads pronto |
| Erros de rede | Tratar exceções de socket | Códigos de status + timeout |

**A frase para a apresentação:** "o gRPC não substitui o socket, ele **usa** o socket e me poupa de escrever o protocolo, a serialização e o controle de conexões".

---

## Ligação com as aulas

| Aula (slides) | Onde aparece no projeto |
| --- | --- |
| Parte 2 – Arquiteturas | Arquitetura cliente/servidor em duas camadas |
| Parte 3 – Processos e threads | Pool de 10 threads no servidor |
| Parte 4 – Comunicação (RPC) | Stubs, marshalling, transparência de acesso, chamada síncrona |
| Parte 5 – Nomeação | Servidor localizado por IP + porta. Não há serviço de nomes: o cliente precisa saber o endereço |
| Parte 6 – Sincronização | Condição de corrida e exclusão mútua com lock |
| Parte 8 – Tolerância a falhas | Timeout, tratamento de servidor indisponível, servidor como ponto único de falha |
| Parte 9 – Segurança | Canal sem TLS e sem autenticação (limitações conscientes) |

### RPC x API web comum (pergunta provável)

As duas resolvem "um programa pedir algo a outro pela rede". A diferença está no **modelo**:
- **API REST (web):** você pensa em **recursos e URLs** (`POST /ingressos`), monta o JSON e interpreta a resposta à mão.
- **RPC:** você pensa em **funções** (`ComprarIngresso(pedido)`). O stub gerado esconde a rede, então a chamada remota se parece com uma local. Com gRPC, ainda há um contrato tipado (`.proto`) e mensagens binárias menores.
