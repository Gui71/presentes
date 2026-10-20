# Chá de casa nova

Lista de presentes de Guilherme e Beatriz, em português do Brasil. Evento em **22/11/2026**; endereço ainda não informado. Django 5.2 LTS, templates HTML, CSS e JavaScript puro, na mesma origem. Sem pagamento ou integração de compra.

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

O superusuário cria contas no Django admin. Para permitir o painel, marque a conta como **ativa** e conceda **Presentes → presente → Pode adicionar presente** (`gifts.add_product`). Não é necessário marcar `Membro da equipe/is_staff`; esse campo sozinho não concede acesso ao painel.

Para cancelar escolhas pelo painel, conceda também **Pode excluir escolha** (`gifts.delete_selection`). Superusuários ativos têm ambas. O admin exige `is_staff` e as permissões próprias do Django; o acesso ao painel não dá acesso ao admin. Não existe cadastro público de gestores. Produtos são criados pelo painel, onde nome e links passam pela extração segura de fotos; o admin mostra seus dados e permite administração geral.

## Visitantes, escolhas e privacidade

- Antes de carregar produtos, o servidor exige apenas nome e primeiro sobrenome. Acentos e grafias legítimas são aceitos. Esses dados não autenticam uma identidade e não concedem permissões administrativas.
- O convidado confirma a escolha no site. Cada produto admite **uma única escolha ativa**, inclusive em confirmações concorrentes; uma pessoa pode escolher vários presentes.
- Os já selecionados vão para o final da lista, ficam esmaecidos e recebem o texto **Já selecionado**. Os nomes aparecem somente aos gestores.
- A confirmação é persistida no banco. Fechar a visita não libera automaticamente os produtos; gestores autorizados podem cancelar escolhas pelo painel ou admin.
- O convidado pode cancelar cada uma das próprias escolhas durante a mesma sessão, preservando as outras e podendo escolher novos itens. O botão aparece apenas nas escolhas da sessão atual. O servidor exige o identificador secreto dessa sessão: **o nome não autoriza cancelamento**, e repeti-lo em outra sessão não dá acesso às escolhas anteriores. Não há token de autorização em localStorage ou armazenamento permanente no navegador.
- As escolhas guardam nome e primeiro sobrenome para consulta exclusiva dos gestores. O identificador de autorização é armazenado como digest no registro da escolha. Quando a sessão se perde, o convidado perde o acesso ao cancelamento; a escolha permanece no banco e pode ser cancelada pelos gestores. Foi expressamente aceita a limitação de que navegadores podem restaurar sessões ao reabrir.

Administradores usam sessão nativa do Django no servidor, cookies HttpOnly/SameSite=Lax e duração do navegador (`set_expiry(0)` nos dois logins). Não há “Lembrar de mim”, JWT ou autenticação em localStorage. Logout exige POST com CSRF e invalida a sessão no banco.

**Fechar o navegador não garante encerrar a sessão:** recursos de restauração podem conservar cookies de sessão e reabrir páginas autenticadas. Testes comprovam que um cookie restaurado ainda funciona; eles não simulam uma garantia de fechamento real. Use **Sair** para invalidar o acesso administrativo. Não há mecanismos baseados em fechar aba, `unload` ou `beforeunload`.

## Cadastro e imagens

O formulário pede só nome do produto e um ou mais links ordenados. `+ outro link` adiciona campos; links adicionais podem ser removidos. Há limite técnico de 10 links por cadastro. A chave de envio impede duplicação por repetição do mesmo formulário e é vinculada à sessão do gestor.

A foto é buscada no primeiro anúncio e, se necessário, nos seguintes. São considerados metadados Open Graph/Twitter relacionados ao nome do produto e JSON-LD `Product` com nome correspondente; não são coletadas imagens arbitrárias da página. A correspondência é uma heurística, não comprovação visual do conteúdo. Bloqueios, CAPTCHA, páginas dependentes de JavaScript, dados ausentes ou falhas de rede resultam em imagem padrão local e aviso no painel; o produto e todos os links são preservados. Não há consulta às lojas durante a visita pública.

Proteções de rede e arquivo:

- Somente HTTP/HTTPS nas portas padrão, sem credenciais, caracteres de controle ou destinos locais. IPv4/IPv6 privados, loopback, link-local, metadados, multicast e endereços de transição são recusados.
- Todos os resultados DNS precisam ser públicos. A conexão usa o IP validado, confere o peer conectado e mantém o hostname original para SNI/verificação TLS. Redirecionamentos e URLs de imagens repetem essas validações; HTTPS não redireciona para HTTP.
- Até quatro redirecionamentos por busca; orçamento global de rede de 12 segundos por cadastro, operações/DNS com até 3 segundos, HTML até 1 MiB, imagem até 5 MiB. DNS lento tem execução limitada e concorrência limitada.
- Somente JPEG, PNG e WebP raster não animados. Limites: 16 milhões de pixels, lado máximo de 8.000 px e mínimo de 48 px. Validação, orientação e recodificação para WebP até 1.000 px, sem metadados do original. SVG/HTML remotos não são servidos como imagem.
- Sem execução de scripts externos, cookies de lojas, contorno de autenticação ou CAPTCHA. Busca só durante cadastro por gestor autorizado, sem endpoint público de extração.

O cliente de extração conecta diretamente a IPs públicos e não usa `HTTP_PROXY/HTTPS_PROXY`, para preservar o vínculo entre DNS validado e destino conectado. Uma hospedagem que só permita egress por proxy precisa de avaliação de transporte antes de habilitar extração por esse caminho; sem conectividade direta, o fallback continua funcionando. Não desative TLS nem a validação de IP para contornar isso.

Lojas são reconhecidas por domínio completo/subdomínio, com registro extensível em `gifts/stores.py`. Há estilos para Mercado Livre, Magalu, Amazon, Casas Bahia e Shopee. Domínios desconhecidos recebem botão neutro e hostname visível. Links externos usam `noopener noreferrer`; não há indicação de parceria, preço ou estoque.

O fundo `static/images/home.webp` foi **gerado para este projeto com a ferramenta de geração de imagens da OpenAI** e otimizado localmente (aproximadamente 145 KB). Não é foto copiada nem hotlink. `house.svg` e `placeholder.svg` são desenhos vetoriais locais do projeto.

## Testes e validação

```bash
python manage.py check
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

## Validação realizada nesta sprint

Base: branch `work`, commit `5d7f05db4ce96571d4b267801257ddb525293d10`, árvore inicialmente limpa e contendo só `AGENTS.md`.

Passaram `check`, `makemigrations --check --dry-run`, **46 testes**, migrações locais, `collectstatic`, a configuração WSGI do Gunicorn e `check --deploy` com valores de produção temporários e seguros. A suíte inclui confirmações concorrentes com um único vencedor, cancelamento individual, recusa de cancelamento por outra sessão com o mesmo nome, permanência da escolha após perder a sessão e a limitação aceita de um cookie restaurado continuar válido.

Playwright com Chromium do sistema verificou desktop/tablet/celular (3/2/1 colunas), identificação, foco/teclado dos modais, confirmação, cancelamento do convidado e do gestor, login/logout, adicionar/remover links, erro de validação e fallback de foto. Não houve erros inesperados de console. Botões principais e de loja verificados tiveram contraste de texto acima de 4,5:1. Os dados usados eram fixtures em banco temporário, separado do banco real, que continua vazio e sem contas predefinidas. Testes de rede usaram mocks, não comprovam extração em lojas reais. Não houve publicação nem validação da hospedagem de produção.
