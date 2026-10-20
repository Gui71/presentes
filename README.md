# Chá de casa nova

Lista de presentes de Beatriz e Guilherme, em português do Brasil. Evento em **22/11/2026**; endereço ainda não informado. Django 5.2 LTS, templates HTML, CSS e JavaScript puro, na mesma origem. Sem pagamento ou integração de compra.

A página inicial tem uma abertura breve com uma ambientação da foto real da sala fornecida pelo usuário, editada nesta conversa com a ferramenta de imagens da OpenAI e servida localmente em `static/images/living-room-splash.webp`. A edição preserva o espaço compacto, as portas, o piso e o ventilador, remove as duas latas de tinta e acrescenta sofá, tapete, TV com painel, mesa pequena e cortina em tons de branco, marrom e cinza. O zoom suave termina em cerca de 2,3 segundos e pode ser pulado pelo botão ou por Escape. A abertura aparece uma vez por aba; `sessionStorage` guarda somente essa preferência visual, sem dados de visitantes ou de autenticação. Movimento reduzido, imagem indisponível ou JavaScript desativado permitem seguir diretamente para a identificação/lista. A imagem de fundo anterior foi preservada.

Conforme esclarecimento do usuário, o copyright e o crédito de desenvolvimento aparecem em todas as páginas, inclusive na administração Django. Os textos são compartilhados por um include e mantidos literalmente. Todo HTML próprio, inclusive includes e templates de subdiretórios, começa com o comentário de copyright/desenvolvimento solicitado; os links de portfólio e LinkedIn ficam apenas no comentário do código-fonte.

## Desenvolvimento

Validado com Python 3.12.14, Django 5.2.18 e SQLite 3.53.1 em Linux. Use Python 3.12 e ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Copie a chave gerada para `SECRET_KEY` em `.env` (sem compartilhá-la ou versioná-la). O marcador do exemplo é rejeitado. Variáveis já exportadas têm prioridade sobre `.env`. Depois:

```bash
python manage.py migrate --noinput
python manage.py createsuperuser
python manage.py runserver
```

A página inicial é a lista; `/login/` abre o login dos gestores, `/painel/` é o cadastro cotidiano e `/admin/` serve para administração geral e concessão de acesso. A lista começa vazia: não há presentes, visitantes ou contas de demonstração em migrations.

No ambiente em nuvem preparado, o ambiente virtual existente fica em `/workspace/.presentes-cloud/venv`; ative-o em vez de criar outro. Cada tarefa já é isolada: use o checkout existente, sem criar worktree salvo pedido explícito.

## Acessos administrativos

O superusuário cria contas no Django admin. Para permitir o painel, marque a conta como **ativa** e conceda `gifts.view_product`. Para cadastrar, conceda também `gifts.add_product`; para editar, `gifts.change_product`; para excluir, `gifts.delete_product`. Não é necessário marcar `Membro da equipe/is_staff`; esse campo sozinho não concede acesso ao painel. As permissões de alteração, exclusão e exportação não são concedidas pelo cadastro.

Para cancelar escolhas pelo painel, conceda também **Pode excluir escolha** (`gifts.delete_selection`). Superusuários ativos têm ambas. O admin exige `is_staff` e as permissões próprias do Django; o acesso ao painel não dá acesso ao admin. Não existe cadastro público de gestores. Produtos são criados pelo painel, com links validados e ilustrações do catálogo local; o admin mostra seus dados e permite administração geral.

## Visitantes, escolhas e privacidade

- Antes de carregar produtos, o servidor exige apenas nome e primeiro sobrenome. Acentos e grafias legítimas são aceitos. Esses dados não autenticam uma identidade e não concedem permissões administrativas.
- O convidado confirma a escolha no site. Cada produto admite **uma única escolha ativa**, inclusive em confirmações concorrentes; uma pessoa pode escolher vários presentes.
- Os já selecionados vão para o final da lista, com ordem estável dentro dos grupos. O card inteiro fica esmaecido, mostra **Já selecionado** e não contém nenhum link de compra/seleção. O cancelamento legítimo fica fora do card e restaura todos os links. Os nomes aparecem somente aos gestores.
- A confirmação é persistida no banco. Fechar a visita não libera automaticamente os produtos; gestores autorizados podem cancelar escolhas pelo painel ou admin.
- O convidado pode cancelar cada uma das próprias escolhas durante a mesma sessão, preservando as outras e podendo escolher novos itens. O botão aparece apenas nas escolhas da sessão atual. O servidor exige o identificador secreto dessa sessão: **o nome não autoriza cancelamento**, e repeti-lo em outra sessão não dá acesso às escolhas anteriores. Não há token de autorização em localStorage ou armazenamento permanente no navegador.
- As escolhas guardam nome e primeiro sobrenome para consulta exclusiva dos gestores. O identificador de autorização é armazenado como digest no registro da escolha. Quando a sessão se perde, o convidado perde o acesso ao cancelamento; a escolha permanece no banco e pode ser cancelada pelos gestores. Foi expressamente aceita a limitação de que navegadores podem restaurar sessões ao reabrir.

Na área dos anfitriões (`/painel/`), a seção **Escolhas confirmadas**, abaixo dos cards, mostra cada presente reservado e o **nome + primeiro sobrenome** informados pelo convidado. Isso exige conta ativa com `gifts.view_product`; a lista pública não mostra esses nomes. Cancelar exige a permissão adicional descrita acima.

Administradores usam sessão nativa do Django no servidor, cookies HttpOnly/SameSite=Lax e duração do navegador (`set_expiry(0)` nos dois logins). Não há “Lembrar de mim”, JWT ou autenticação em localStorage. Logout exige POST com CSRF e invalida a sessão no banco.

**Fechar o navegador não garante encerrar a sessão:** recursos de restauração podem conservar cookies de sessão e reabrir páginas autenticadas. Testes comprovam que um cookie restaurado ainda funciona; eles não simulam uma garantia de fechamento real. Use **Sair** para invalidar o acesso administrativo. Não há mecanismos baseados em fechar aba, `unload` ou `beforeunload`.

## Cadastro e imagens

O formulário contém nome do produto, links de compra ordenados (até 10) e o seletor opcional de ilustração. O seletor mostra os nomes genéricos das 47 artes e começa em **Automática pelo nome**. A chave de envio impede duplicação do mesmo cadastro e é vinculada à sessão do gestor.

Por escolha explícita de custo zero de API, usamos **47 ilustrações geradas nesta conversa com a ferramenta de imagens da OpenAI**, armazenadas no catálogo local. O site não chama OpenAI, fal.ai ou Pollinations, não consulta anúncios e não executa inferência na VM. A assinatura Plus é separada da API; não há chave de geração para configurar nem serviço pago a habilitar.

Ao cadastrar um presente com nome reconhecido ou ilustração escolhida no seletor, o servidor valida o asset e salva uma cópia em `MEDIA_ROOT`. Links curtos, opacos, indisponíveis ou com rastreamento não afetam a imagem. Nomes vagos, ambíguos ou objetos não cobertos ficam com o padrão local até uma escolha manual no catálogo. Não se escolhe uma imagem aleatória nem se interpreta o anúncio pela URL.

Imagens válidas existentes são preservadas. Alterar links não refaz a imagem; alterar o nome preserva o arquivo atual e pode mostrar um aviso de revisão. Para um item antigo sem imagem, use **Usar ilustração**. Para substituir uma imagem, use **Rever ilustração**, confira a prévia e confirme. A operação exige `gifts.view_product` + `gifts.change_product`, POST/CSRF e a versão atual do item. Uma seleção ativa permanece intacta; edição/exclusão da identidade do presente continuam bloqueadas.

O reconhecimento aceita maiúsculas/minúsculas misturadas, acentos, pontuação e flexões controladas de singular/plural dos tipos conhecidos, incluindo **panela/panelas**, **copo/copos** e **talher/talheres**. Nomes específicos como **panela de pipoca** têm prioridade sobre o tipo genérico contido na mesma expressão. Para diagnosticar um nome, rode `python manage.py check_illustrations --name "panela"`; sem `--name`, o comando verifica apenas os arquivos. Erros de digitação arbitrários e objetos desconhecidos exigem escolha manual ou inclusão de uma nova arte.

Se o nome não for reconhecido, use **Escolher ilustração** no painel, selecione um nome genérico, clique em **Ver prévia** e confirme em **Usar esta ilustração**. A escolha manual persiste e tem prioridade sobre o nome; editar nome/links preserva essa escolha e a foto. Para retornar ao modo automático, selecione **Automática pelo nome**, revise e confirme; sem correspondência, a foto e a escolha anteriores ficam preservadas.

Esta atualização inclui a migration `0006_product_illustration_choice`, que preserva presentes, imagens e escolhas dos convidados. Aplique as migrations no procedimento de atualização documentado. Reconstrua/recrie o app Docker ou reinicie Django/Gunicorn para carregar as regras, pois o catálogo fica em cache por processo. Nos itens antigos sem imagem, aplique a ilustração pelo painel.

O painel mostra se há ilustração compatível, se uma imagem anterior foi preservada ou se o nome mudou. Não há fila nem status de geração online: aplicar um arquivo local é uma operação curta. Repetir uma aplicação já concluída reutiliza o arquivo. Erros preservam o cadastro e a imagem anterior; edição/exclusão concorrente impede aplicar um resultado obsoleto e arquivos novos sem referência são limpos.

As imagens de IA são identificadas nos cards e são genéricas: **marca, modelo, cor e quantidade exatos devem ser conferidos nos anúncios**. A lista enviada para preparar o catálogo não cria presentes automaticamente. Consulte [IMAGENS-CATALOGO.md](IMAGENS-CATALOGO.md) para objetos cobertos, nomes reconhecidos, origem e como incluir novos objetos em uma atualização manual.

Os assets são WebP até 1.000 px, sem metadados do original, com SHA-256 no manifesto, tamanho limitado e validação do raster antes do uso. As cópias dos presentes continuam privadas, servidas pela rota Django após identificação/acesso administrativo, e precisam do backup de mídia. As fontes do catálogo são versionadas junto do código e incluídas no build.

Links continuam validados como HTTP/HTTPS público, sem credenciais, portas arbitrárias ou IPs literais locais. O cadastro não resolve DNS nem busca seu conteúdo. O transporte anterior em `gifts.external` conserva as proteções de SSRF/TLS e seus testes, mas não é chamado pelo novo fluxo. Lojas continuam reconhecidas por domínio completo/subdomínio; destinos desconhecidos têm botão neutro. Links abrem com `noopener noreferrer`.

O fundo aprovado `static/images/home.webp` permanece idêntico. Ele também foi gerado para este projeto com a ferramenta de imagens da OpenAI. `house.svg` e `placeholder.svg` são desenhos locais.

## Testes e validação

```bash
python manage.py check
python manage.py check_illustrations
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Os testes usam exclusivamente `.test.sqlite3`, criado e removido pelo runner; o banco normal não é usado. O arquivo permite exercitar concorrência real entre conexões SQLite. Testes de fotos simulam HTTP, DNS e lojas, sem depender de serviços externos.

Para `check --deploy`, use as configurações de produção abaixo com uma chave temporária forte, hosts/origens HTTPS de validação e banco local. HSTS pode ser ativado temporariamente apenas para conferir os checks; isso não comprova a infraestrutura real. Não execute migrações em produção sem autorização e backup.

```bash
python manage.py check --deploy
```

Esse comando deve rodar com `APP_ENV=production`, `DEBUG=false`, `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` explícitos e as opções de segurança apropriadas ao HTTPS real. Alertas de HSTS são esperados enquanto ele estiver desligado; a ativação depende da infraestrutura.

## Produção no seu servidor

Não houve publicação nem inspeção da hospedagem. Prepare:

1. Linux/Python 3.12, dependências de `requirements.txt` e segredo forte fornecido pelo ambiente. `APP_ENV=production`, `DEBUG=false`, `ALLOWED_HOSTS=seu-dominio` e `CSRF_TRUSTED_ORIGINS=https://seu-dominio`. Hosts curinga, DEBUG em produção, segredo ausente/fraco/marcador e origens de produção não HTTPS são rejeitados.
2. SQLite em disco persistente local, fora da pasta pública, com backup consistente; adequado a uma lista pequena e baixa concorrência. Mantenha o arquivo e seu diretório graváveis pelo usuário da aplicação. Para carga maior ou múltiplos servidores, planeje a mudança de banco em tarefa própria; PostgreSQL não está configurado nesta sprint.
3. `MEDIA_ROOT` persistente e privado; as fotos são entregues pela rota Django que verifica a identificação/acesso do gestor. **Não exponha `/media/` diretamente pelo proxy.** Use backup conjunto de banco e mídia.
4. Execute `collectstatic` e sirva apenas `STATIC_ROOT` em `/static/` pelo servidor HTTP. Nunca exponha a raiz do projeto, `.env`, banco ou mídia como diretório público.
5. WSGI com Gunicorn, por exemplo, a partir da raiz: `gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2 --timeout 45`. O processo não serve estáticos em produção. `config/asgi.py` também está disponível caso um servidor ASGI seja escolhido posteriormente.
6. Proxy reverso com HTTPS, encaminhamento correto de Host, certificados válidos e reinício supervisionado. `TRUST_PROXY_HTTPS=true` só se o proxy remover o cabeçalho `X-Forwarded-Proto` do cliente e definir seu próprio valor. HSTS começa desativado; avalie subdomínios/preload antes de configurar as três variáveis correspondentes.

Cookies Secure e redirecionamento HTTPS são automáticos em produção; desenvolvimento com `APP_ENV=development` mantém HTTP funcional. CSP restringe recursos do site à própria origem, protege contra framing e scripts inline; o Django admin mantém seus recursos nativos. Todas as respostas de aplicação têm `Cache-Control: private, no-store`, inclusive páginas protegidas.

Os dois logins compartilham o bloqueio **django-axes em banco**, compatível com workers distintos: cinco falhas por IP, pausa de 15 minutos e reset após login bem-sucedido. O endereço vem exclusivamente de `REMOTE_ADDR`, sem confiar em `X-Forwarded-For`. Atrás de proxy, isso pode agrupar clientes no IP do proxy; ajuste o transporte de IP real apenas com configuração conhecida e confiável. Registros do bloqueador são privados; não são expostos nos logs públicos. Limpeza de sessões: `python manage.py clearsessions`; use os comandos administrativos do django-axes quando precisar limpar bloqueios.

## Decisões alinhadas

Confirmação exclusiva no site, vários presentes por convidado, nomes apenas para gestores, cancelamento por gestores autorizados e cancelamento individual do próprio convidado na mesma sessão. Foi aceita explicitamente a possibilidade de restauração de cookies pelo navegador. Não há expiração automática da escolha, integração de compra ou cancelamento autorizado somente pelo nome.

## Validação da primeira sprint

Base: branch `work`, commit `5d7f05db4ce96571d4b267801257ddb525293d10`, árvore inicialmente limpa e contendo só `AGENTS.md`.

Passaram `check`, `makemigrations --check --dry-run`, **46 testes**, migrações locais, `collectstatic`, a configuração WSGI do Gunicorn e `check --deploy` com valores de produção temporários e seguros. A suíte inclui confirmações concorrentes com um único vencedor, cancelamento individual, recusa de cancelamento por outra sessão com o mesmo nome, permanência da escolha após perder a sessão e a limitação aceita de um cookie restaurado continuar válido.

Playwright com Chromium do sistema verificou desktop/tablet/celular (3/2/1 colunas), identificação, foco/teclado dos modais, confirmação, cancelamento do convidado e do gestor, login/logout, adicionar/remover links, erro de validação e fallback de foto. Não houve erros inesperados de console. Botões principais e de loja verificados tiveram contraste de texto acima de 4,5:1. Os dados usados eram fixtures em banco temporário, separado do banco real, que continua vazio e sem contas predefinidas. Testes de rede usaram mocks, não comprovam extração em lojas reais. Não houve publicação nem validação da hospedagem de produção.

## Gestão, exportações e ampliação atual

O atalho público de anfitriões foi removido; digite `/login` ou `/login/` diretamente. O fundo e as cores foram preservados. A escala de fontes usa rem, base de 18px e controles de pelo menos 16px, com reflow em desktop/celular e texto ampliado.

Editar abre modal com nome e links ordenados preenchidos e preserva imagens existentes. Mudanças nos links não consultam lojas nem refazem ilustrações. Usar/Rever ilustração permite aplicar o catálogo local com prévia, permissão e confirmação, sem alterar a escolha. Excluir exige confirmação com o nome do item e remove links/foto após commit. Reenvio de exclusão concluída é idempotente.

**Edição e exclusão são bloqueadas enquanto houver escolha ativa.** Primeiro um gestor autorizado cancela a escolha. Versão do registro, escrita atômica e relação protegida impedem alterar/apagar silenciosamente uma escolha concorrente. Migrations são incrementais e preservam produtos, links e escolhas. Para manter os gestores existentes, a migration acrescenta view_product a usuários/grupos que já tinham add_product; nenhuma permissão de edição/exclusão/exportação é acrescentada.

Downloads no painel (POST com CSRF, sem parâmetros de caminho):

- Banco `.db`: inicialmente superusuário; delegação exige `gifts.view_product` + `gifts.export_database`. Usa o backend/caminho real das configurações, backup online da API SQLite, integridade verificada, temporário privado e limpeza ao fechar a resposta. Inclui os dados privados do banco, portanto delegue somente a responsáveis pelos backups. Mídia e .env não fazem parte do arquivo.
- Conferência `.xlsx`: inicialmente superusuário; delegação exige `gifts.view_product` + `gifts.export_selections`. Apenas nome + primeiro sobrenome e presente ativo. Uma linha por escolha, sem fundir homônimos; cancelamentos não aparecem. Valores são células de texto literal, inclusive se começarem por sinais de fórmula. Planilha vazia mantém os dois cabeçalhos.

`python manage.py backup_database` e `backup_media` escrevem backup em stdout para redirecionamento privado. `import_snapshot` e `import_media` importam de stdin somente para destinos vazios e recusam sobrescrita. Consulte **[DEPLOY-DOCKER-ORACLE.md](DEPLOY-DOCKER-ORACLE.md)** para comandos completos, Docker/Caddy não root, volumes, HTTPS, migrações controladas, transferência, backup/restauração e rollback. O reset é artefato opcional separado: não está no repositório, build ou deploy e foi testado apenas em bancos temporários.

### Histórico do diagnóstico das fotos (sprint anterior)

Foi reproduzido com um servidor HTTP de teste um erro real: após consumir uma resposta com Connection: close/Content-Length, o loop tentava reajustar o timeout no socket já fechado, descartando a imagem válida. O loop agora verifica o término da resposta antes de usar o socket. O teste verifica HTML comprimido, URL relativa, download de imagem real e recodificação para WebP, em vez de aceitar só o placeholder. Metadados adicionais receberam testes próprios. A proteção de IP conectado, TLS, redirects e os limites continuam ativos.

Os três exemplos enviados (Amazon B07WGQ64QR, Magalu gk6k991a5g e Mercado Livre MLB44200947) foram tentados nesta nuvem. A resolução DNS direta falhou antes do HTTP, e o proxy retornou 403 de política de rede. Isso não permite afirmar que as fotos dessas lojas foram obtidas aqui; bloqueios/CAPTCHA também não são contornados. Na sprint seguinte, o usuário escolheu substituir a dependência dessas buscas por um catálogo de ilustrações geradas na conversa, sem API paga. O cadastro/edição atual não chama esse extrator.

Base desta ampliação: `a735c34d8a47cd52fb84f9fcdef86b5a0e169f19` (master com PR anterior incorporado). Passaram 67 testes em Python nativo e os mesmos 67 na imagem Docker, além de 5 testes do reset separado em bancos temporários. Também passaram check, migrations incrementais, ausência de migrations pendentes, collectstatic, preload do Gunicorn e check --deploy com configuração temporária de produção.

Playwright verificou navegação pública, seleção/cancelamento e remoção/restauração de links, edição/exclusão em modais, downloads, grade 3/2/1, controles ampliados, reflow com texto a 200%, foco/teclado e console sem erros inesperados. A revisão visual cobriu desktop e celular, com fixtures privadas em banco temporário. Docker/Compose foram validados em AMD64 com build, configuração, HTTPS local confiando na CA do Caddy e persistência de produto, escolha e foto WebP após recriação dos containers. Arquivos privados responderam 404 pelo proxy. A infraestrutura OCI, ARM64 e o certificado do domínio real não foram executados/validados nesta tarefa.

## Sprint do catálogo de ilustrações

Base: `edc97883a57e66f3ff68945ef7aa5b6a71440383`, master após o PR de gestão/exportações. O usuário optou por ilustrações geradas nesta conversa e reutilizadas localmente, sem integração de API paga. Foram produzidas e revisadas 47 artes, com correspondências que cobrem os tipos de objeto da lista fornecida. Presentes reais não foram criados a partir dessa lista.

Passaram **84 testes nativos e os mesmos 84 na imagem Docker**, incluindo arquivos inválidos, correspondência de nomes, ausência de rede, confirmação de substituição, preservação de imagens anteriores, deduplicação, permissões/CSRF e edição/exclusão concorrente. Passaram também check, check_illustrations, migrations locais preservando os dados, ausência de migrations pendentes, collectstatic, Gunicorn preload e check --deploy com valores temporários de produção.

Playwright verificou imagens geradas, legenda, prévia e confirmação/cancelamento da troca, cadastro/edição sem requests externos, seleções/cancelamento, grade 3/2/1, celular, foco, texto a 200% e console limpo. Docker foi reconstruído em AMD64 e validado com HTTPS local confiável e persistência da foto anterior, da ilustração aplicada, dos metadados e das escolhas após recriação. Os testes de navegador usaram banco/mídia temporários, sem alterar o banco normal. O script de reset separado ficou intocado; não houve publicação na Oracle.
