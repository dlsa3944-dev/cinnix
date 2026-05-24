# Cinnix 1.0

Um desktop Cinnix com estilo visual **Luminix**, feito em Python com Tkinter.

O projeto inclui fluxo de boot, instalador em terminal, OOBE, tela de bloqueio, desktop com janelas, menu, barra inferior, apps integrados, sistema de arquivos interno, terminal, navegador com acesso HTTP/HTTPS real via biblioteca padrao do Python e temas claro/escuro.

## Requisitos

- Python 3.10 ou superior
- Tkinter instalado
- Internet opcional, usada pelo navegador e pelos comandos `curl`, `wget` e `ping`

No Windows, Tkinter normalmente ja vem com o Python oficial. Para testar:

```powershell
python -m tkinter
```

## Como Rodar

Abra o terminal na pasta do projeto e execute:

```powershell
python system.py
```

## Primeiro Uso

Ao iniciar, o sistema passa por etapas parecidas com um sistema real:

1. Boot/carregamento com mensagens de inicializacao.
2. Instalador em terminal.
3. OOBE, configurando idioma, teclado, fuso horario, usuario, senha e tema.
4. Tela de bloqueio/login.
5. Desktop Cinnamon/Luminix.

## Instalador Em Terminal

Na tela do instalador, voce pode usar:

```text
help
lsblk
check
install
reboot
```

Use `install` para executar a instalacao. Depois disso, o sistema segue para a configuracao inicial.

## Apps Incluidos

O menu inclui apps como:

- Nemo
- Cinnamon Settings
- Update Manager
- Driver Manager
- Software Manager
- Timeshift
- System Monitor
- Firewall Configuration
- Firefox
- Thunderbird
- Transmission
- Remmina
- Warpinator
- Celluloid
- Rhythmbox
- Pix
- Xreader
- LibreOffice Writer, Calc, Impress, Draw e Base
- Xed
- Terminal
- Archive Manager
- Calculator
- Disks
- USB Image Writer
- Font Viewer
- Sticky Notes
- Calendar
- Bluetooth Manager

## Navegador

O Firefox interno acessa HTTP/HTTPS reais usando `urllib.request`.

Exemplos:

```text
https://example.com
https://www.python.org
https://duckduckgo.com/html/?q=Cinnix
```

Ele renderiza paginas como texto em modo leitura, lista links encontrados e permite salvar a pagina no sistema de arquivos interno.

## Terminal

O terminal possui comandos basicos:

```text
help
clear
pwd
ls
cd
cat
echo
touch
mkdir
rm
date
whoami
neofetch
theme
open
apps
history
nano
curl
wget
ping
exit
```

Exemplos:

```bash
ls /Home/Documents
cat /Home/Documents/welcome.txt
open firefox
curl https://example.com
curl https://example.com > pagina.txt
wget https://example.com
ping example.com
```

## Sistema De Arquivos

O projeto usa um sistema de arquivos interno em memoria. Apps como Nemo, Terminal, Xed, Timeshift, Screenshot, LibreOffice e Firefox compartilham esse mesmo estado durante a execucao.

Exemplos de caminhos:

```text
/Home/Documents
/Home/Downloads
/Home/Pictures
/System
/Trash
```

## Observacoes

Cinnix 1.0 e uma implementacao em Tkinter com recursos locais e acesso HTTP/HTTPS basico, pensada para estudar interface desktop, janelas, apps integrados e fluxos de sistema operacional em Python puro.

## Licenca

Distribuido sob a licenca MIT. Veja [LICENSE](LICENSE).
