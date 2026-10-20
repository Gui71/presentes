# Docker e Oracle Cloud — Chá de casa nova

Consulta às referências oficiais: **20/10/2026**. Este guia prepara um deploy manual; nenhuma VM, regra OCI, domínio ou publicação foi criada por esta tarefa. Use os caminhos e serviços abaixo com os arquivos deste repositório.

## Arquitetura e pré-requisitos

`compose.yaml` contém uma réplica `app` (Django/Gunicorn, UID/GID 10001) e `proxy` (Caddy, UID/GID 10001). Só o proxy publica portas: host 80 → container 8080 e host 443 → container 8443. `app:8000` fica na rede do Compose. A rede permite saída para anúncios públicos; não há banco de rede nem docker.sock montado.

Volumes: `app_database` guarda **o diretório inteiro** `/var/lib/presentes/db`, incluindo WAL/SHM se usados; `app_media` guarda `/var/lib/presentes/media`; `caddy_data` e `caddy_config` preservam certificados/configuração do proxy. O nome padrão do projeto é `presentes`; mantenha-o estável. Os estáticos são coletados no build e copiados para `/srv/static` na imagem do proxy. A mídia é privada e servida pelas views Django autorizadas, nunca por diretório público do Caddy.

Docker Engine e Compose plugin atuais (Compose **2.24.4+** por causa de `!override` no teste local), Git, Python 3 para preparar configuração, disco persistente e acesso HTTPS aos registries/PyPI. Planeje pelo menos 2 GiB de RAM para build e aplicação pequena, mais espaço para imagens, banco, mídia e backups; meça sua carga. Não há promessa de gratuidade ou capacidade da OCI. SQLite fica em disco local de uma única VM/réplica; não escale a aplicação para outros servidores compartilhando esse arquivo.

O caminho principal é **Ubuntu Server 24.04 LTS padrão** (ainda suportado), listado nas imagens da OCI para x86 e Arm. Confira a imagem disponível na sua região/shape no momento da criação; para Arm use Ubuntu padrão, não Minimal. As imagens oficiais Python/Caddy têm variantes AMD64/ARM64; nesta tarefa a execução foi em AMD64. Em Arm valide build e testes na própria arquitetura antes da publicação.

## 1. Preparação no computador local

No Windows, use WSL2 com integração do Docker Desktop e execute estes comandos no shell Linux; mantenha código/arquivos privados no filesystem do WSL. No Linux, use Engine + Compose plugin. Para instalar no Ubuntu, use o procedimento oficial da seção seguinte. Confira:

```bash
docker version
docker compose version
git clone https://github.com/Gui71/presentes.git
cd presentes
```

Repositório privado exige autenticação do Git configurada no computador/servidor. Nunca coloque token na URL, `.env` de build, Dockerfile ou imagem. Confira que o commit desejado já foi incorporado antes de clonar/atualizar a produção.

Prepare `.env` privado sem sobrescrever um arquivo existente:

```bash
umask 077
test -e .env || cp .env.example .env
python3 - <<'PY'
from pathlib import Path
import secrets
p = Path('.env')
lines = p.read_text().splitlines()
for i, line in enumerate(lines):
    if line.startswith('SECRET_KEY=') and ('CHANGE-ME' in line or line == 'SECRET_KEY='):
        lines[i] = 'SECRET_KEY=' + secrets.token_urlsafe(64)
p.write_text('\n'.join(lines) + '\n')
p.chmod(0o600)
PY
```

Para o teste local, ajuste no arquivo `SITE_DOMAIN=localhost`, `CSRF_TRUSTED_ORIGINS=https://localhost:8443`. O Compose força `APP_ENV=production`, `DEBUG=false`, hosts explícitos e cookies Secure; é um teste HTTPS com CA local, sem certificado público. `compose.local.yaml` publica somente em loopback do host Docker.

```bash
docker compose -p presentes-local -f compose.yaml -f compose.local.yaml config --quiet
docker compose -p presentes-local -f compose.yaml -f compose.local.yaml build
docker compose -p presentes-local -f compose.yaml -f compose.local.yaml run --rm --no-deps app python manage.py migrate --noinput
docker compose -p presentes-local -f compose.yaml -f compose.local.yaml run --rm --no-deps app python manage.py createsuperuser
docker compose -p presentes-local -f compose.yaml -f compose.local.yaml up -d --no-build
docker compose -p presentes-local -f compose.yaml -f compose.local.yaml ps
docker compose -p presentes-local -f compose.yaml -f compose.local.yaml cp proxy:/data/caddy/pki/authorities/local/root.crt /tmp/presentes-local-ca.crt
curl --cacert /tmp/presentes-local-ca.crt https://localhost:8443/healthz/
```

Abra `https://localhost:8443/`. Para teste no navegador, instale **somente o certificado público** da CA local no perfil de teste ou use um contexto de navegador com essa CA confiável. Não desative TLS para testar dados reais; não copie a chave privada da CA. A criação de administrador é interativa, sem senha predefinida. Caddy não instala a CA automaticamente (`skip_install_trust`). No teste local o redirect HTTP aponta à porta HTTPS pública padrão; use a URL HTTPS com 8443 diretamente. Em produção, o redirect corresponde à porta 443 publicada.

Se houver proxy corporativo com CA própria, a instalação de dependências no build exige a cadeia de confiança correspondente. O Dockerfile aceita `--secret id=build_ca,src=/caminho/ca-bundle-confiavel.pem`; ela é montada só durante `pip install`, sem ir para a imagem final. Em Compose, use um override privado de build/secrets ou construa os targets `app` e `proxy` com `docker build --secret ... --target ... -t <nome-do-projeto>-app/proxy .`. Não use `--trusted-host`, `-k` ou desative verificação de certificados.

## 2. Criar a VM e a rede na OCI (console, sem comandos locais)

Antes de criar recursos, confira custos, quotas, capacidade da região/availability domain e boot volume persistente adequado. Selecione Compute → Instances → Create instance e Ubuntu 24.04 LTS padrão. Confira a arquitetura da shape: AMD64/x86_64 ou ARM64/aarch64. Ao entrar no servidor, confirme `uname -m`, `/etc/os-release`, `free -h` e `df -h`; não deduza recursos pelo nome da shape.

Use uma VCN com **subnet pública**, Internet Gateway e rota `0.0.0.0/0` para esse gateway. O wizard “Create VCN with Internet Connectivity” pode criar a estrutura; revise suas regras. Associe um IP público à VNIC, preferencialmente reservado para manter DNS estável. Não configure AAAA sem ter IPv6/rotas/firewall efetivamente funcionais.

Gere uma chave SSH local se não possuir uma:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/presentes_oci
```

Proteja a chave privada com passphrase; envie **apenas a chave pública** `.pub` à criação da VM. Ubuntu da OCI normalmente usa o usuário `ubuntu`; confira a instrução de conexão da imagem selecionada. Nos comandos seguintes, substitua `<IP_PUBLICO_OCI>`, `<CIDR_ADMINISTRATIVO>` e `<DOMINIO_REAL>` pelos valores reais; são placeholders, não valores descobertos.

Revise **NSGs e todas as Security Lists** aplicadas à VNIC/subnet. Permissões se somam: um NSG restrito não neutraliza uma Security List que ainda permita SSH de qualquer origem. Permita TCP 22 somente do CIDR administrativo, TCP 80 e 443 públicos, preservando regras essenciais de retorno, ICMP/PMTU e tráfego OCI necessário. Não abra 8000, banco, daemon Docker ou portas de administração. Preserve saída DNS e HTTP/HTTPS necessária para atualizações, ACME e imagens de produtos.

## 3. Preparar Ubuntu via SSH

**No computador local:**

```bash
ssh -i ~/.ssh/presentes_oci ubuntu@<IP_PUBLICO_OCI>
```

**Daqui em diante no servidor SSH:**

```bash
cat /etc/os-release
uname -m
free -h
df -h
sudo apt update
sudo apt upgrade -y
sudo apt install -y ca-certificates curl git python3 nano
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
sudo docker run --rm hello-world
```

Procedimento para VM nova sem Docker concorrente. Se já houver Engine/containerd/podman, inventarie os serviços e siga a remoção de pacotes conflitantes da documentação oficial antes de instalar; não desinstale infraestrutura existente cegamente. Use `sudo docker` nos passos de servidor abaixo. O grupo `docker` equivale a controle de root no host; não é exigido por este guia.

Revise o firewall do SO junto com as regras OCI. Se usar UFW, permita primeiro SSH do CIDR administrativo e 80/443, confirmando outra sessão SSH antes de habilitá-lo. **Portas publicadas pelo Docker podem contornar UFW**: a restrição de borda deve estar correta em NSGs/Security Lists e na configuração de portas do Compose. Não limpe iptables, não desative o gerenciamento de firewall do Docker e preserve regras essenciais da imagem OCI. Ajustes de `DOCKER-USER` dependem do firewall/backend real e exigem revisão própria.

## 4. Código e configuração privada no servidor

```bash
sudo install -d -o ubuntu -g ubuntu -m 0750 /srv/presentes
git clone https://github.com/Gui71/presentes.git /srv/presentes
cd /srv/presentes
git rev-parse HEAD
umask 077
test -e .env || cp .env.example .env
```

Gere a chave pelo bloco Python da seção 1 e edite com `nano .env`: `APP_ENV=production`, `DEBUG=false`, `SITE_DOMAIN=<DOMINIO_REAL>`, `ALLOWED_HOSTS=<DOMINIO_REAL>`, `CSRF_TRUSTED_ORIGINS=https://<DOMINIO_REAL>`, `TRUST_PROXY_HTTPS=true`. Compose define os caminhos finais do banco/mídia/estáticos e força as opções seguras. Não use wildcard para hosts/origens. O segredo é lido em runtime por `env_file`; não entra no build.

Crie o registro DNS A do domínio para o IP público. Espere a resolução correta; remova/corrija AAAA incorreto. Portas públicas 80/443 precisam alcançar o proxy. Caddy emite e renova certificados automaticamente para o domínio real. Seus volumes persistentes contêm material privado de certificado e devem ser protegidos. HSTS começa desligado; ative as três variáveis correspondentes somente após validar HTTPS e conhecer o efeito sobre todos os subdomínios/preload.

O Caddy encaminha Host e define seus próprios `X-Forwarded-*`, ignorando valores forjados recebidos de clientes. Como app não publica portas e o único proxy de entrada é este Caddy, `TRUST_PROXY_HTTPS=true` é apropriado nesta arquitetura. Não habilite essa confiança em outra topologia sem verificá-la. O bloqueio de login usa `REMOTE_ADDR`; atrás do proxy, as tentativas podem compartilhar o IP do Caddy. Não passe a confiar em `X-Forwarded-For` cegamente para alterar isso.

## 5. Primeira instalação vazia

```bash
cd /srv/presentes
sudo docker compose config --quiet
sudo docker compose build
sudo docker compose run --rm --no-deps app python manage.py migrate --noinput
sudo docker compose run --rm --no-deps app python manage.py createsuperuser
sudo docker compose run --rm --no-deps app python manage.py check --deploy
sudo docker compose up -d --no-build
sudo docker compose ps
sudo docker compose logs --tail=100 app proxy
```

Migrations são etapa controlada, nunca entrypoint automático. Estáticos já são coletados durante o build; reconstruir ambos os targets atualiza Django e CSS/JS no proxy. `check --deploy` pode alertar sobre HSTS ainda desligado; não ignore outros alertas. Não use `runserver`, não aumente `app` para múltiplas réplicas e não publique sua porta interna. Arquivos não root usam UID/GID 10001 e ownership dos volumes; não aplique `chmod 777`.

## 6. Transferir banco/mídia existentes, sem reset

Pare o sistema de origem para obter um conjunto banco+mídia correspondente ao mesmo momento. Gere snapshot consistente com `python manage.py backup_database > /caminho/privado/banco.db` e mídia com `python manage.py backup_media > /caminho/privado/midia.tar.gz`. Preserve o `.env` de origem privadamente; use a mesma SECRET_KEY se precisar manter sessões/capacidades existentes, sabendo que cookies de outro domínio não serão automaticamente transferidos.

Transfira os arquivos por SCP/SSH para um diretório privado fora do checkout, por exemplo `/home/ubuntu/presentes-transferencia` (modo 0700). Não os envie ao Git nem à imagem. No servidor, **antes de migrate/up e em volumes vazios**:

```bash
cd /srv/presentes
sudo docker compose build
sudo docker compose run --rm --no-deps -T app python manage.py import_snapshot < /home/ubuntu/presentes-transferencia/banco.db
sudo docker compose run --rm --no-deps -T app python manage.py import_media < /home/ubuntu/presentes-transferencia/midia.tar.gz
sudo docker compose run --rm --no-deps app python manage.py migrate --noinput
sudo docker compose run --rm --no-deps app python manage.py check
sudo docker compose up -d --no-build
```

Os importadores recusam banco existente/mídia não vazia; não substituem dados. Se já iniciou a stack com dados, faça backup e use um projeto/volumes novos para restauração, conforme seção 8. Não apague dados para contornar a recusa. A migration de permissões mantém acesso de leitura dos gestores que já tinham cadastro, sem conceder edição/exclusão/exportações.

## 7. Validação externa e persistência

**No computador local**, com o domínio real:

```bash
curl -I http://<DOMINIO_REAL>/
curl -I https://<DOMINIO_REAL>/
curl https://<DOMINIO_REAL>/healthz/
curl -I https://<DOMINIO_REAL>/.env
curl -I https://<DOMINIO_REAL>/media/qualquer-arquivo
curl -I https://<DOMINIO_REAL>/reset_total.py
```

Espere redirect HTTP→HTTPS, certificado válido, health `ok` e recusa dos arquivos privados. Não use `-k`. Pelo navegador, verifique identificação, login direto `/login/`, fontes ampliadas, desktop/mobile/zoom 200%, cadastro/edição/exclusão de item livre, bloqueio de item selecionado, seleção/cancelamento, fotos, snapshot `.db` e planilha `.xlsx` com autorização. Teste perfil sem permissões. Confira que a porta 8000 não aparece em `docker compose ps` como porta publicada e não é acessível externamente. Não abra banco/backup em endpoint estático para testá-lo.

Depois de cadastrar dados de verificação autorizados, confira persistência:

```bash
sudo docker compose up -d --force-recreate --no-build
sudo docker compose ps
```

Confirme os mesmos dados/mídia e certificados. O daemon habilitado no systemd mais `restart: unless-stopped` reinicia serviços após reboot; teste reboot em janela controlada, com backup. **Não use `docker compose down -v` nem remova volumes em procedimentos normais.**

## 8. Backup e restauração isolada

Backups incluem banco, mídia e configuração privada. A exportação `.db` do painel não contém os arquivos de imagens nem `.env`. Guarde cópias cifradas fora da VM e teste restauração. Para um conjunto consistente, interrompa escritas durante o backup conjunto:

```bash
cd /srv/presentes
umask 077
BACKUP_DIR="$HOME/presentes-backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
sudo docker compose stop proxy app
sudo docker compose run --rm --no-deps -T app python manage.py backup_database > "$BACKUP_DIR/banco.db"
sudo docker compose run --rm --no-deps -T app python manage.py backup_media > "$BACKUP_DIR/midia.tar.gz"
sudo docker compose run --rm --no-deps -T --entrypoint tar proxy -czf - -C /data . > "$BACKUP_DIR/caddy-data.tar.gz"
sudo docker compose run --rm --no-deps -T --entrypoint tar proxy -czf - -C /config . > "$BACKUP_DIR/caddy-config.tar.gz"
cp .env "$BACKUP_DIR/configuracao.env"
chmod 600 "$BACKUP_DIR/"*
sudo docker compose up -d --no-build
```

Confira que os comandos terminaram com sucesso e valide o SQLite com `PRAGMA integrity_check`. Os arquivos Caddy incluem chaves privadas; proteja-os como o `.env`. Para restaurar certificados na mesma identidade/domínio, com proxy parado e volumes novos, use o serviço `proxy` com `--entrypoint tar -xzf - -C /data` (e `/config`), lendo somente seus próprios arquivos de backup confiáveis; não extraia arquivos de procedência desconhecida. Não use `cp` do banco ativo: o comando fornecido usa `sqlite3.Connection.backup()`, incluindo dados confirmados em WAL. Para **testar restauração de dados**, no computador local ou VM isolada com `.env` HTTPS local, use outro projeto com volumes novos e uma CA local própria, sem importar chaves privadas de produção:

```bash
docker compose -p presentes-restore -f compose.yaml -f compose.local.yaml build
docker compose -p presentes-restore -f compose.yaml -f compose.local.yaml run --rm --no-deps -T app python manage.py import_snapshot < /caminho/privado/banco.db
docker compose -p presentes-restore -f compose.yaml -f compose.local.yaml run --rm --no-deps -T app python manage.py import_media < /caminho/privado/midia.tar.gz
docker compose -p presentes-restore -f compose.yaml -f compose.local.yaml run --rm --no-deps app python manage.py migrate --noinput
docker compose -p presentes-restore -f compose.yaml -f compose.local.yaml up -d --no-build
```

Pare outro proxy local que esteja usando 8080/8443 antes. Confirme usuários, permissões, escolhas ativas e fotos. Não faça esse teste sobre volumes de produção. Para recuperar produção, prepare e valide um novo conjunto de volumes com o snapshot correto, preserve os volumes antigos, pare a stack antiga e faça o corte em janela controlada; não substitua arquivos enquanto houver processos usando-os.

## 9. Atualizar, diagnosticar e reverter

Antes de atualizar: faça e valide backup conjunto, registre `git rev-parse HEAD` e o nome do projeto/volumes. Depois:

```bash
cd /srv/presentes
git pull --ff-only
sudo docker compose build
sudo docker compose stop proxy app
sudo docker compose run --rm --no-deps app python manage.py migrate --noinput
sudo docker compose run --rm --no-deps app python manage.py check
sudo docker compose up -d --no-build
sudo docker compose ps
sudo docker compose logs --tail=100 app proxy
```

Logs têm rotação de 10 MiB × 3 por serviço. Não publique `.env`, exports ou dumps de `docker compose config` com valores; use `config --quiet`. Em falha de permissão, confira UID/GID 10001 e ownership do diretório/volume correto; não amplie permissões globalmente. Em 502, confira health/migrations/logs do app. Em loop de redirect, confira topologia do proxy e HTTPS. Em falha ACME, confira DNS/AAAA, 80/443, NSGs/Security Lists/firewall e certificados persistentes. Em foto ausente, diferencie aviso de extração, arquivo ausente, DNS/egress, CAPTCHA/403 e rota de mídia autorizada; use “Tentar foto novamente” com permissão de alteração. Não contorne controles da loja nem reduza SSRF/TLS.

Rollback exige compatibilidade entre código e estado do banco. Não execute migrações reversas ou restaure snapshot cegamente: confirme o plano da alteração. Se for preciso restaurar, use o procedimento em volumes novos e considere as escritas feitas desde o backup. Mantenha o commit/imagens anteriores até validar a nova versão; não reescreva histórico Git.

## 10. Reset opcional — só testes, artefato separado

`reset_total.py` é entregue fora do repositório e não está na imagem. Não integra nenhum comando de deploy ou inicialização. Para teste local isolado, com os processos parados:

```bash
python /caminho/privado/reset_total.py --project-root /caminho/do/projeto --backup-dir /caminho/privado/fora-do-projeto/backups --dry-run
```

Confira ambiente e caminhos. Na execução real, acrescente `--processes-stopped` e digite a frase exata mostrada; sem terminal, forneça `--confirm 'RESET TOTAL /caminho/absoluto/do/banco.sqlite3'`. Por padrão preserva mídia; apagar mídia exige também `--remove-media --confirm-media 'APAGAR MIDIA /caminho/absoluto/da/media'` e gera backup separado antes da remoção. Produção é recusada. Depois execute `createsuperuser`; senha não é gerada pelo script.

Em Docker, use **uma stack de testes separada**, parada, alterando explicitamente `APP_ENV=test`, `DEBUG=false` e caminhos de volumes de teste. Monte o arquivo como bind **somente de leitura** em um container `app` descartável, junto de um diretório de backup privado externo; execute com `--project-root /app --backup-dir /reset-backups`, primeiro `--dry-run`. Um exemplo de `compose run` é: `docker compose -p presentes-teste run --rm --no-deps -e APP_ENV=test -v /caminho/privado/reset_total.py:/tools/reset_total.py:ro -v /caminho/privado/backups:/reset-backups app python /tools/reset_total.py --project-root /app --backup-dir /reset-backups --dry-run`. O host deve permitir UID 10001 acessar apenas esse diretório privado. Não monte o script em containers de produção nem use volumes de produção neste procedimento.

## Referências oficiais consultadas

- [Django 5.2 — checklist de deploy](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/) e [fonte oficial da documentação](https://github.com/django/django/blob/stable/5.2.x/docs/howto/deployment/checklist.txt).
- [Docker Engine no Ubuntu](https://docs.docker.com/engine/install/ubuntu/) e [fonte oficial consultada](https://github.com/docker/docs/blob/main/content/manuals/engine/install/ubuntu.md).
- [Docker: firewall e UFW](https://docs.docker.com/engine/network/packet-filtering-firewalls/), [Compose services](https://docs.docker.com/reference/compose-file/services/).
- [Caddy reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy), [HTTPS automático e CA local](https://caddyserver.com/docs/automatic-https).
- [OCI: criar instância](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm), [imagens de plataforma suportadas](https://docs.oracle.com/en-us/iaas/Content/Compute/References/images.htm).
- [Ubuntu: ciclo de suporte](https://ubuntu.com/about/release-cycle).

Disponibilidade de shapes, capacidade, valores e regras da sua conta precisam ser verificados na OCI. Certificado público e validação externa do domínio só podem ser confirmados após o deploy autorizado.
