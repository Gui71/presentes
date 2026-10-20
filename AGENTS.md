# AGENTS.md — Chá de casa nova

## Contexto e arquitetura

Projeto independente para um chá de casa nova: os anfitriões estão se mudando, não se casando. Idioma: português do Brasil.

Stack definida: Python + Django com templates HTML, CSS e JavaScript puro, em um único projeto e na mesma origem. Templates: lista.html, login.html e painel.html. CSS, JS e imagens em static/; imagens de produtos armazenadas em media/ ou armazenamento equivalente documentado. SQLite no desenvolvimento. Banco e hospedagem de produção dependem do ambiente real.

Preferir Django 5.2 LTS com patch de segurança atualizado e Python compatível, verificando suporte e compatibilidade antes de fixar dependências. Evitar SPA, DRF, JWT, microsserviços ou infraestrutura adicional sem necessidade demonstrada.

## Protocolo de trabalho

1. Ler este arquivo integralmente e todos os AGENTS.md aplicáveis aos caminhos alterados.
2. Inspecionar repositório, documentação, dependências, git status, branch e git rev-parse HEAD. Informar o commit base encontrado; se não houver commits, declarar isso.
3. Analisar os arquivos relevantes antes de alterar. Preservar alterações preexistentes.
4. Apresentar plano em etapas para tarefas complexas.
5. Resolver escolhas técnicas rotineiras dentro do escopo. Quando faltar regra de negócio ou houver instruções incompatíveis, perguntar antes da implementação dependente e continuar o trabalho independente.
6. Implementar, validar e relatar resultados reais. Nunca afirmar teste, pesquisa, geração de imagem ou compatibilidade que não foi verificada.

## Regras de Ouro (NUNCA QUEBRAR)

- Não usar linguagem, imagens ou funcionalidades de casamento.
- Não inventar nomes dos anfitriões, endereço, data, regras de reserva, pagamentos ou quantidades de presentes.
- A página inicial é a lista; antes dos presentes, exigir apenas nome e primeiro sobrenome do visitante em modal.
- Nome informado pelo visitante não autentica sua identidade nem concede permissões.
- Exibir três cards por linha no desktop, duas no tablet e um no celular.
- Cadastro de presentes: somente superusuário e usuários ativos autorizados explicitamente no backend.
- Manter o painel próprio para cadastro; Django admin fica para administração geral e concessão de acessos.
- O formulário do item contém apenas Nome do produto e Inserir link do anúncio, repetível por + outro link. Não adicionar campos de preço, descrição, categoria ou upload de foto.
- Tentar obter a foto pelo primeiro link; se falhar, tentar os seguintes na ordem. Falhas externas não podem impedir o cadastro.
- Nunca expor credenciais, sessões, nomes de visitantes ou detalhes internos desnecessários nas respostas públicas.
- Versionar .env.example; ignorar .env e arquivos locais com segredos.
- Versionar o requirements.txt com todas as bibliotecas necessárias, vou rodar o sistema no meu servidor na nuvem, então já deixe preparado para tal.
- Não apagar dados, reescrever histórico, alterar infraestrutura ou publicar sem autorização específica.
- Nome dos anfitriões "Guilherme" e "Beatriz", endereço ainda sem, data 22/11/2026.
- Um item ao ser selecionado e confirmado pela pessoa deve ficar no final da lista esmaecido com um texto cinza "Já selecionado", não permitindo duplicidade.
- A mesma pessoa pode selecionar mais de um item, deixe isso explicito no topo da lista de presentes.

## Autenticação e segurança

- Usar autenticação e hashing de senhas nativos do Django, sessões no servidor e tokens CSRF. Não persistir autenticação em localStorage nem criar login público de administradores.
- O superusuário concede permissões pelo Django admin. Acesso ao painel próprio não deve, por si só, conceder acesso ao admin; is_staff isoladamente não autoriza o cadastro.
- Verificar autenticação, usuário ativo e permissões em todas as views e operações protegidas.
- Aplicar cookie de duração do navegador às sessões administrativas, inclusive Django admin, usando set_expiry(0) nos fluxos de login ou mecanismo equivalente verificado. Não oferecer Lembrar de mim.
- Documentar que a restauração de sessões do navegador pode preservar cookies: não prometer detecção infalível do fechamento. Não usar beforeunload, unload ou fechamento de aba como garantia de logout.
- Logout por POST com CSRF e invalidação da sessão no servidor. Páginas protegidas com Cache-Control: no-store.
- Cookie de sessão HttpOnly e SameSite adequado; HTTPS e cookies Secure em produção. Desenvolvimento HTTP local deve continuar funcional.
- Proteger os dois logins contra tentativas abusivas, com solução compatível com múltiplos processos e sem confiar cegamente em cabeçalhos de proxy.
- Manter CSRF ativo, escape de templates, validação no servidor, ORM e redirecionamentos pós-login seguros. Não inserir nomes ou metadados externos como HTML.
- SECRET_KEY por ambiente, sem segredo fixo de fallback; DEBUG desativado em produção; ALLOWED_HOSTS e origens CSRF explícitos.
- Configurar cabeçalhos de segurança compatíveis com os recursos usados. HSTS e confiança em proxy exigem configuração conhecida do ambiente.
- Não coletar CPF, telefone ou e-mail dos visitantes. Não registrar senhas, cookies, tokens ou dados pessoais desnecessários em logs.

## Links externos e imagens

- A extração de metadados ocorre no backend, somente a pedido de usuário autorizado e sem criar proxy público de URLs.
- Validar esquema HTTP/HTTPS, hostname e porta. Bloquear credenciais na URL, localhost, redes privadas, loopback, link-local, metadados de nuvem e demais destinos não públicos, em IPv4 e IPv6.
- Aplicar a mesma proteção às páginas, imagens e redirecionamentos. Validar o destino efetivamente conectado para evitar DNS rebinding; uma checagem DNS separada não basta.
- Limitar tempo total, tentativas, redirecionamentos, bytes e dimensões de imagens. Verificar TLS; não contornar CAPTCHA, autenticação ou bloqueios das lojas.
- Tratar HTML e metadados como dados não confiáveis; nunca executar scripts externos. Validar e recodificar imagens raster antes de armazená-las; não servir HTML/SVG remoto como foto.
- Identificar loja por hostname normalizado e correspondência correta de domínio, nunca por substring. Links desconhecidos recebem botão neutro.
- Processar e armazenar a imagem no cadastro, evitando consultas às lojas em cada visita pública. Usar imagem padrão local quando necessário.
- Links de compra abrem em nova aba com rel="noopener noreferrer".

## Validação e entrega

Criar migrations para alterações de modelos e testes focados nos fluxos, permissões, sessões, CSRF e extração segura de imagens. Simular serviços externos nos testes.

Executar ao final:

    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py test
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    python manage.py check --deploy

Executar migrações apenas em banco local/de validação; nunca presumir autorização para banco de produção. Rodar check --deploy com configurações de produção e valores temporários seguros, sem publicar. Corrigir problemas de código/configuração e explicar dependências reais de infraestrutura.

Verificar visualmente desktop e celular, modais, teclado, foco, contraste e ausência de erros no console. Se alguma ferramenta não estiver disponível, informar a limitação.

Entregar código, migrations, testes, requirements.txt, .env.example, .gitignore, imagens e README com instalação, criação do superusuário, concessão de permissões, execução, testes e requisitos de produção. Relatar arquivos alterados, validações, limitações e decisões pendentes.
