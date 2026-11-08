# 2. Instalação e execução, passo a passo

Ordem sugerida: **(A)** rodar tudo no seu Windows → **(B)** rodar Windows + WSL (já é Windows conversando com Linux!) → **(C)** no laboratório, notebook + PC Linux.

Comandos de terminal aparecem em blocos assim: copie e cole uma linha por vez.

---

## A. No seu Windows

### A1. Instalar o Python

1. Baixe o Python 3.12 ou mais novo em <https://www.python.org/downloads/>.
2. Na primeira tela do instalador, **marque "Add python.exe to PATH"** e clique em *Install Now*.
3. Abra um **novo** PowerShell e confira:

   ```powershell
   python --version
   ```

   Se abrir a Microsoft Store em vez de mostrar a versão, feche e use `py --version`. Neste caso, troque `python` por `py` em todos os comandos.

### A2. Preparar a pasta do projeto

1. Descompacte o projeto, por exemplo em `C:\Users\SeuNome\trabalho-ingressos`.
2. Abra a pasta no VS Code (*File > Open Folder*) e abra o terminal integrado (*Terminal > New Terminal*), ou abra o PowerShell e entre na pasta:

   ```powershell
   cd C:\Users\SeuNome\trabalho-ingressos
   ```

### A3. Criar um ambiente virtual e instalar o gRPC

O **ambiente virtual (venv)** é uma "caixinha" com as bibliotecas só deste projeto, sem bagunçar o Python do computador.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

- Depois de ativar, o terminal mostra `(venv)` no começo da linha. **Ative sempre** que abrir um terminal novo para o projeto.
- Se aparecer *"a execução de scripts foi desabilitada neste sistema"*, rode uma vez o comando abaixo e tente ativar de novo:

  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```

### A4. Gerar os stubs a partir do contrato

```powershell
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ingressos.proto
```

O que esse comando faz: lê o `ingressos.proto` (`-I.` = procure arquivos nesta pasta) e gera `ingressos_pb2.py` (mensagens) e `ingressos_pb2_grpc.py` (stubs). Os arquivos já vêm no projeto, mas **gere de novo em cada máquina**: assim eles batem com a versão do gRPC instalada ali.

### A5. Rodar

Abra **dois** terminais (os dois com o venv ativado):

```powershell
# Terminal 1
python servidor.py
```

```powershell
# Terminal 2
python cliente.py
```

- Na primeira vez, o Windows pode mostrar o alerta do **Firewall** pedindo permissão para o Python. Marque **Redes privadas e Redes públicas** e clique em *Permitir acesso*. Isso já prepara a etapa entre duas máquinas.
- Teste as 10 opções do menu. Depois rode `python teste_concorrencia.py` com o servidor normal e com `python servidor.py --sem-trava`.
- Para desligar o servidor: `Ctrl + C`.
- Para começar com os dados zerados: desligue o servidor e apague o `dados.json`.

### A6. Socket puro (para entender a base)

```powershell
cd socket_eco
python servidor_eco.py      # terminal 1
python cliente_eco.py       # terminal 2
```

---

## B. Windows + WSL (Linux) no mesmo notebook

O WSL 2 roda um Linux de verdade, com rede própria, então já é uma comunicação **Windows ↔ Linux**. Também é o **plano B** se a rede do laboratório não colaborar.

### B1. Preparar o Python no WSL

No terminal do Ubuntu (WSL):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

A pasta do Windows aparece dentro do Linux em `/mnt/c/`:

```bash
cd /mnt/c/Users/SeuNome/trabalho-ingressos
python3 -m venv venv-linux          # outro venv: o do Windows não funciona no Linux
source venv-linux/bin/activate
pip install -r requirements.txt
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ingressos.proto
```

### B2. Rodar

```bash
# No WSL (Linux): servidor
python servidor.py
```

```powershell
# No PowerShell (Windows): cliente
python cliente.py localhost
```

O WSL 2 repassa o `localhost` do Windows para o Linux, então o cliente encontra o servidor. Inverter também funciona (servidor no Windows, cliente no WSL), mas aí use o IP do Windows que aparece na tela do servidor.

---

## C. Duas máquinas na faculdade (notebook Windows + PC Linux)

### C1. Antes de sair de casa (checklist)

- [ ] Projeto funcionando no notebook (parte A).
- [ ] Projeto em um pendrive **e** no GitHub (para baixar no PC do laboratório).
- [ ] Regra de firewall criada (C3).
- [ ] Plano B testado (parte B).

### C2. No PC Linux do laboratório

```bash
python3 --version                    # anote a versão
cd ~/Downloads/trabalho-ingressos    # ou onde você copiou
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ingressos.proto
```

Se der problema:

| Problema | Solução |
| --- | --- |
| `python3 -m venv` falha (falta `python3-venv` e você não tem `sudo`) | Pule o venv e instale só para seu usuário: `python3 -m pip install --user -r requirements.txt` |
| Sem `pip` ou sem internet no laboratório | Leve os pacotes no pendrive (C6) |
| Python 3.9 ou mais antigo | O `pip` instala uma versão antiga do gRPC sozinho. Só **gere os stubs de novo** (comando acima), senão aparece erro de versão |

### C3. Liberar a porta 50051 no Windows (firewall)

Abra o PowerShell **como administrador** (botão direito > *Executar como administrador*):

```powershell
New-NetFirewallRule -DisplayName "gRPC Ingressos 50051" -Direction Inbound -Protocol TCP -LocalPort 50051 -Action Allow -Profile Any
```

Isso diz ao "porteiro" do Windows: deixe entrar conexões TCP na porta 50051, em qualquer tipo de rede. Redes de faculdade costumam ser classificadas como **públicas**, por isso o `-Profile Any`. Depois da apresentação, se quiser remover a regra:

```powershell
Remove-NetFirewallRule -DisplayName "gRPC Ingressos 50051"
```

### C4. Descobrir o IP do servidor

O `servidor.py` já mostra o IP na tela ("Em outra máquina: python cliente.py 192.168..."). Para conferir:

- **Windows:** `ipconfig` → procure *Adaptador de Rede sem Fio Wi-Fi* (ou *Ethernet*) → **Endereço IPv4**.
- **Linux:** `hostname -I`.

### C5. Testar a conexão antes de rodar o cliente

Atenção: **não use `ping` contra o Windows** para testar. O Windows bloqueia ping por padrão, então ele falha mesmo com tudo certo.

Teste a **porta**, do PC Linux para o notebook (só usa Python, sem instalar nada):

```bash
python3 -c "import socket; socket.create_connection(('192.168.0.15', 50051), 3); print('PORTA ABERTA')"
```

- `PORTA ABERTA`: pode rodar `python cliente.py 192.168.0.15`.
- `timed out`: o pacote não chega. É firewall ou isolamento da rede.
- `Connection refused`: chegou na máquina, mas o servidor não está rodando.

Do Windows para o Linux, o equivalente é `Test-NetConnection 192.168.0.20 -Port 50051`.

### C6. Plano B, C e D (se a rede da faculdade bloquear)

Redes Wi-Fi de universidade costumam **isolar** os aparelhos entre si, e os PCs do laboratório ficam no cabo, muitas vezes em outra rede. Se o teste C5 falhar:

| Plano | Como | Ainda é Windows ↔ Linux? |
| --- | --- | --- |
| B | Pergunte se o notebook pode usar um cabo de rede do laboratório (mesma rede dos PCs) | Sim |
| C | Servidor em um PC Linux e cliente em outro PC Linux do laboratório | Não, mas são duas máquinas reais |
| D | Notebook sozinho: servidor no WSL, cliente no Windows (parte B) | Sim, na mesma máquina |

**Pacotes no pendrive (se o laboratório não tiver internet):** no seu Windows, com o venv ativado, baixe os pacotes para Linux. Troque `3.10` pela versão do Python do laboratório:

```powershell
pip download grpcio grpcio-tools --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.10 -d pacotes_linux
```

No laboratório:

```bash
python3 -m pip install --user --no-index --find-links pacotes_linux grpcio grpcio-tools
```

---

## D. Wireshark: vendo os pacotes de verdade

1. Baixe em <https://www.wireshark.org/download.html> e instale. Aceite instalar o **Npcap** e marque a opção de capturar tráfego de *loopback* (para ver o `localhost`).
2. Abra o Wireshark e escolha a interface:
   - Teste na mesma máquina: **Adapter for loopback traffic capture**.
   - Duas máquinas: a placa **Wi-Fi** ou **Ethernet** que tem o IP do servidor.
3. No campo de filtro, digite `tcp.port == 50051` e aperte Enter. Faça uma compra no cliente.
4. Se os pacotes aparecerem só como "TCP", clique com o botão direito em um deles → **Decode As...** → porta 50051 → **HTTP2**.

**O que mostrar e explicar:**

| No Wireshark | O que é |
| --- | --- |
| `[SYN]`, `[SYN, ACK]`, `[ACK]` | O aperto de mão do TCP abrindo a conexão |
| Portas `53422 → 50051` | Porta efêmera do cliente → porta do servidor |
| `HEADERS` com `:path /ingressos.VendaIngressos/ComprarIngresso` | A chamada RPC: qual função está sendo chamada |
| `DATA` / `GRPC Message` com `yago` e `B4` legíveis | A mensagem Protobuf. É legível porque o canal é **sem TLS** (gancho para a aula de segurança) |
| `[ACK]` depois de cada envio | O TCP confirmando o recebimento (por isso é confiável) |
| `[FIN]` | Fechamento da conexão ao sair do cliente |

Para o socket puro, use o filtro `tcp.port == 5000`, clique com o botão direito → **Follow > TCP Stream** e veja a mensagem e a resposta em texto.

---

## E. Git e GitHub (lembretes rápidos)

Para guardar o projeto e mostrar no LinkedIn.

```bash
git init
git add .
git commit -m "Sistema de venda de ingressos com gRPC"
```

Crie um repositório vazio no GitHub (botão **New**) e siga os comandos que ele mostra, que são parecidos com estes:

```bash
git remote add origin https://github.com/yagowelsing/ingressos-grpc.git
git branch -M main
git push -u origin main
```

O arquivo `.gitignore` do projeto já impede de subir o `venv`, o `__pycache__` e o `dados.json`.

No dia a dia, depois de mudar algo: `git add .` → `git commit -m "o que mudou"` → `git push`.

---

## F. Problemas comuns

| Mensagem | Causa provável | O que fazer |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'grpc'` | venv não ativado ou pacotes não instalados | Ative o venv e rode `pip install -r requirements.txt` |
| `No module named 'ingressos_pb2'` | Stubs não gerados ou terminal fora da pasta do projeto | Rode o comando de geração (A4) dentro da pasta |
| Erro citando versão do `grpcio` ou `protobuf` | Stubs gerados com uma versão diferente da instalada | Gere os stubs de novo nesta máquina |
| `[REDE] Servidor indisponível` | Servidor desligado, IP errado ou firewall | Confira o servidor, o IP e o teste C5 |
| `Address already in use` / porta em uso | Já tem um servidor rodando | Feche o outro terminal ou `Ctrl + C` nele |
| Acentos estranhos no terminal do Windows | Página de código antiga | Use o terminal do VS Code ou o *Windows Terminal* |
