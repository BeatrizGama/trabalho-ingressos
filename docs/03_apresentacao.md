# 3. Apresentação, perguntas prováveis e divulgação

## Seu calendário até 11/11

| Quando | O que fazer | Pronto quando |
| --- | --- | --- |
| Hoje, 01/11 | Ler `01_conceitos.md`, instalar (parte A do guia), rodar tudo e ler o código com os comentários. Rodar a parte B (WSL) | Você consegue explicar a "viagem de uma compra" sem olhar |
| Sexta, 06/11 | Teste no laboratório (parte C do guia), com o checklist C1 feito antes | Cliente do PC Linux comprando no servidor do notebook, ou um plano B escolhido |
| Fim de semana, 07 e 08/11 | Montar os slides, ensaiar com cronômetro 2 vezes, responder em voz alta as perguntas abaixo, subir no GitHub | Apresentação em até 14 minutos |
| 09 e 10/11 | Só revisão leve (você tem o TCC no dia 11) | |
| Quarta, 11/11 | Apresentação | |

---

## Roteiro de 15 minutos

O enunciado pede: **ferramentas e tecnologias usadas** + **breve demonstração**.

| Tempo | Slide / ação | O que falar |
| --- | --- | --- |
| 0:00 – 1:00 | **Título e problema** | "Venda de ingressos com escolha de assento. O problema central de sistemas distribuídos aqui: várias pessoas, em máquinas diferentes, disputando o mesmo assento." |
| 1:00 – 3:00 | **Arquitetura** (diagrama cliente → stub → rede → stub → servidor → JSON) | Cliente/servidor, RPC, onde ficam os stubs, porta 50051 |
| 3:00 – 5:30 | **Ferramentas e tecnologias** | Python, gRPC, Protobuf (12 bytes x 52 em JSON), HTTP/2 sobre TCP, threads + lock, JSON. Por que gRPC e não socket puro / XML-RPC / RMI |
| 5:30 – 6:30 | **A API** (tabela das 10 funções) | 6 no estilo do enunciado + 4 extras. Mostrar o `.proto` rapidamente |
| 6:30 – 11:30 | **Demonstração ao vivo** | Ver roteiro da demo abaixo |
| 11:30 – 13:00 | **Concorrência explicada** | Condição de corrida, a trava, ligação com a aula de sincronização |
| 13:00 – 14:00 | **Limitações e próximos passos** | Sem TLS (mostrado no Wireshark), sem login, servidor único (replicação) |
| 14:00 – 15:00 | Encerramento / perguntas | |

### Roteiro da demonstração (5 minutos)

Deixe tudo aberto **antes** de começar: servidor no notebook, cliente no PC Linux, Wireshark com o filtro `tcp.port == 50051`.

1. **Mostrar que são duas máquinas:** `ipconfig` no Windows e `hostname -I` no Linux.
2. **Cliente no Linux:** listar eventos (1), ver mapa do evento 1 (2), comprar o B4 (3). No terminal do servidor aparece a chamada com o IP do PC Linux.
3. **Erro de negócio:** tentar comprar o B4 de novo → "Assento já vendido". Tentar o evento 4 → "Evento já aconteceu".
4. **Extras rápidos:** transferir o ingresso para outra pessoa (8) e validar na portaria (9) duas vezes → "Ingresso já usado".
5. **Wireshark:** pausar a captura e mostrar o handshake, o `:path` com o nome da função e o "yago" / "B4" legíveis nos bytes.
6. **Concorrência:** reiniciar o servidor com `--sem-trava`, rodar `teste_concorrencia.py` → 10 aprovadas. Reiniciar normal, rodar de novo → 1 aprovada.
7. **Falha:** desligar o servidor (`Ctrl + C`) e tentar uma opção no cliente → mensagem de servidor indisponível.

Se a rede do laboratório falhar no dia, faça a mesma demo com o plano D (WSL + Windows) e diga isso com naturalidade: "a rede do laboratório isola os aparelhos, então vou mostrar Windows ↔ Linux usando o WSL".

---

## Perguntas prováveis (com respostas curtas)

**1. O que é RPC?**
Chamar uma função que executa em outro computador como se fosse local. O stub esconde a rede: empacota os parâmetros, envia, espera e desempacota a resposta.

**2. O que é o stub no seu projeto?**
O `ingressos_pb2_grpc.py`, gerado pelo `protoc`. No cliente, o `VendaIngressosStub` tem um método para cada função; no servidor, o `VendaIngressosServicer` é o esqueleto que eu completo com a lógica.

**3. Por que gRPC e não socket direto?**
Com socket eu teria que inventar o protocolo, serializar e tratar conexões à mão (mostro no `socket_eco`). O gRPC usa socket por baixo, mas gera esse código a partir do contrato e me deixa focar nas regras.

**4. Por que gRPC e não Java RMI?**
RMI só funciona entre programas Java. O gRPC é independente de linguagem e sistema, e é o padrão atual do mercado.

**5. O que acontece na rede quando o cliente compra?**
Serialização em Protobuf → HTTP/2 POST para `/ingressos.VendaIngressos/ComprarIngresso` → segmentos TCP (com handshake se for a primeira chamada) → pacotes IP até o servidor → o sistema entrega à porta 50051 → o gRPC desserializa e uma thread executa a função → a resposta volta pelo mesmo caminho.

**6. Por que TCP e não UDP?**
Numa compra não pode faltar nem embaralhar nenhum byte. O TCP garante entrega completa e em ordem; o UDP não. O gRPC, inclusive, é construído sobre TCP.

**7. Como o servidor atende vários clientes ao mesmo tempo?**
Com um pool de 10 threads. Cada chamada que chega vai para uma thread livre.

**8. O que é a condição de corrida que você mostrou?**
Várias threads verificam o assento ao mesmo tempo, todas veem "livre" e todas vendem. A trava torna "verificar + vender" uma operação única: uma thread por vez.

**9. Por que duas travas?**
A `trava_dados` protege a estrutura (ninguém escreve no dicionário ou no arquivo ao mesmo tempo). A `trava_venda` protege a regra de negócio (a verificação e a venda acontecem juntas). Com só a primeira, cada escrita é segura, mas a decisão continua baseada num dado velho.

**10. E se o servidor cair?**
O cliente não trava: tem timeout de 5 segundos e mostra "servidor indisponível". Os dados não se perdem porque estão no `dados.json`. Mas o sistema fica parado: o servidor é um ponto único de falha. A solução seria replicação.

**11. É seguro?**
Não, de propósito, e isso aparece no Wireshark. O canal não usa TLS, então os dados vão legíveis, e o usuário não é autenticado. Para produção: `secure_channel` com certificados e login com token.

**12. Qual a diferença para uma API REST?**
REST pensa em recursos e URLs com JSON; RPC pensa em funções. O gRPC ainda tem contrato tipado e mensagens binárias menores.

**13. Por que a porta 50051? E o 0.0.0.0?**
50051 é a porta usada nos exemplos oficiais do gRPC e não exige administrador. O 0.0.0.0 faz o servidor aceitar conexões de qualquer placa de rede; com 127.0.0.1 só a própria máquina conectaria.

**14. Onde está a transparência no seu sistema? E onde ela "vaza"?**
Está no `stub.ComprarIngresso(...)`, que parece uma chamada local. Vaza nas falhas: uma função local nunca dá "servidor indisponível" nem precisa de timeout.

---

## Para o LinkedIn e o currículo

**Linha para o currículo (seção Projetos):**

> **Sistema distribuído de venda de ingressos (Python, gRPC, Protobuf)** – API RPC com 10 operações e servidor multithread com controle de concorrência que impede venda duplicada de assentos; comunicação entre Windows e Linux; testes de carga concorrente e análise de tráfego com Wireshark.

**Rascunho de post (ajuste com suas palavras e coloque um vídeo curto da demo):**

> Neste semestre, em Sistemas Distribuídos na UFRRJ, desenvolvi um sistema de venda de ingressos com escolha de assento usando Python e gRPC.
>
> O desafio mais interessante: o que acontece quando 10 pessoas tentam comprar o mesmo assento no mesmo instante? Sem sincronização, o sistema vendeu o mesmo lugar 10 vezes. Com um lock bem posicionado, só uma compra passa.
>
> O que aprendi na prática:
> 🔹 RPC e stubs gerados a partir de um contrato (.proto)
> 🔹 Serialização com Protocol Buffers sobre HTTP/2 e TCP
> 🔹 Condição de corrida e exclusão mútua em servidor multithread
> 🔹 Comunicação entre Windows e Linux e análise dos pacotes no Wireshark
>
> Código no GitHub: [link]
> #SistemasDistribuidos #gRPC #Python #UFRRJ
