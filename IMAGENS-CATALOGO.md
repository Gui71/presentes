# Ilustrações locais, sem API paga

O usuário escolheu **gerar ilustrações nesta conversa com ChatGPT/Codex e reutilizá-las no site**. O catálogo contém 62 imagens genéricas: as 47 artes anteriores produzidas com a ferramenta de imagens da OpenAI e 15 PNGs fornecidos pelo usuário em `15imagensnovassite.zip`, reaproveitados em 28/10/2026. Não houve nova geração nem chamada de API para esta ampliação. Não atribuímos um modelo de geração não verificado.

As 15 imagens anexadas foram revisadas visualmente e convertidas para WebP de até 1.000 px, sem alterar o conteúdo ilustrado. O manifesto preserva o nome e o SHA-256 de cada PNG de origem, além do hash do WebP. SHA-256 do ZIP: `81c0a219a17c91a012466d3775a7b9331031c87f2e7c6cb40de9f0793ea58940`. As 47 fontes anteriores permanecem intactas. Esta atualização acrescenta apenas opções ao catálogo e ao seletor: nenhum presente, imagem aplicada ou reserva existente é alterado automaticamente.

O site lê arquivos locais: não gera novas imagens, não consulta lojas, não envia dados ao provedor e não executa inferência na VM. Não há chave, créditos, cobrança de API, fila, worker ou thread de geração. Criar novas artes no ChatGPT/Codex segue os limites do plano do usuário.

## Usar no painel

1. Cadastre nome e links de compra. Deixe **Ilustração (opcional)** em **Automática pelo nome** ou selecione um objeto pelos nomes genéricos do catálogo. Ao salvar, a imagem escolhida aparece no card; links curtos ou indisponíveis não interferem.
2. Em item existente, use **Usar ilustração**, **Escolher ilustração** (se o nome não for reconhecido) ou **Rever ilustração** (se já houver imagem).
3. O seletor lista somente os nomes dos objetos. Escolha um e clique em **Ver prévia**. Só **Usar esta ilustração** confirma a aplicação. A imagem anterior permanece até a operação concluir.

A ação exige conta ativa, `gifts.view_product` e `gifts.change_product`, além de POST/CSRF. A atribuição inicial faz parte do cadastro autorizado por `add_product`. Trocar apenas a imagem não muda nome, links ou seleção. Edição/exclusão do presente continuam bloqueadas enquanto houver escolha ativa. A lista fornecida para criar o catálogo não foi inserida no banco como presentes ou quantidades.

Uma escolha manual tem prioridade sobre o nome e fica salva, inclusive após editar nome/links ou reiniciar o app. A edição de nome/links mantém a imagem e não muda essa escolha; use **Rever ilustração** para trocá-la. Para voltar ao reconhecimento pelo nome, selecione **Automática pelo nome**, confira a prévia e confirme. Se não houver correspondência automática, a escolha e a imagem anteriores são preservadas.

O painel mostra se há ilustração compatível, escolhida manualmente, se uma imagem anterior foi preservada ou se o nome mudou no modo automático e exige revisão. Falhas preservam o cadastro e a imagem anterior ou padrão. Repetir uma aplicação concluída reutiliza o arquivo. Não há botão “Gerar novamente”, pois o site não oferece geração online.

As artes têm legenda **Imagem ilustrativa gerada por IA**. Confira marca, modelo, cor, acessórios e quantidade exatos nos anúncios. Uma arte pode ilustrar itens distintos do mesmo tipo sem unir seus registros ou reservas.

## Correspondência, segurança e persistência

`gifts/illustrations/catalog.json` registra chave, nome, aliases, exclusões, SHA-256, descrição visual e origem dos arquivos. A comparação ignora acentos, maiúsculas/minúsculas (inclusive misturadas), pontuação e preposições de ligação, e reconhece as flexões singular/plural dos objetos e qualificadores do catálogo. Continua usando palavras/frases completas; não há scraping nem interpretação da URL por IA.

Por exemplo, **panela**, **PANELAS** e **PaNeLa** reconhecem o tipo genérico de panelas; **panela de pipoca** prioriza a pipoqueira específica e **panela de pressão** prioriza a nova arte própria. **copo/copos**, **prato/pratos**, **talher/talheres**, **açucareiro/acucareiros** e os demais tipos possuem variações testadas. Marcas, quantidades e cores complementares não precisam coincidir com os aliases.

Nomes vagos como “Presente”, códigos de anúncio, objetos não cobertos e nomes que correspondem a mais de um tipo ficam com a imagem padrão e permitem escolha manual. “Kit panelas e liquidificador” não escolhe arbitrariamente um deles. Variantes e peças não cobertas também são recusadas no modo automático, por exemplo “Copo para liquidificador”, “Toalhas de mesa” e “Cafeteira italiana”. Flexões conhecidas são tratadas; erros de digitação arbitrários, sinônimos não cadastrados e objetos ausentes não têm reconhecimento garantido. Nesses casos, o seletor permite escolher uma das artes existentes sem depender do nome.

Fontes em `gifts/illustrations/assets/` são incluídas pelo `COPY gifts` do Dockerfile e não têm uma rota pública de diretório. São WebP não animados, até 1.000 px, sem metadados do PNG original. Antes da aplicação, validamos hash, tamanho máximo de 1 MiB, formato real e dimensões. O navegador não escolhe arquivo, caminho ou endpoint.

O banco guarda a preferência manual (`illustration_choice`, vazia no modo automático), chave/hash da arte aplicada e o caminho da cópia em `MEDIA_ROOT`. A escolha aceita somente chaves do catálogo validado; caminhos, URLs e valores desconhecidos são recusados no backend. Essa cópia continua servida pela view Django protegida; o Caddy não expõe `/media/`. O snapshot `.db` não inclui imagens: preserve mídia, banco e configuração privada no backup. Recriar containers mantém a mídia no volume `app_media`.

A migration `0006_product_illustration_choice` acrescenta a preferência vazia aos presentes anteriores, sem alterar imagens, links ou reservas. Execute `python manage.py migrate --noinput` na atualização controlada do servidor. Edições preservam arquivos válidos; mudar só links não refaz a imagem. Uma edição/exclusão concorrente invalida a aplicação antiga pela versão do produto, sem recriar registros. Arquivos antigos só são removidos após commit e arquivos novos sem referência são limpos em falha.

Verificação local, sem alterar presentes:

```bash
python manage.py check_illustrations
python manage.py check_illustrations --name "jogo de talher"
python manage.py check_illustrations --name "toalhas"
python manage.py check_illustrations --name "panela"
python manage.py test --noinput
```

No Docker:

```bash
sudo docker compose run --rm --no-deps app python manage.py check_illustrations
sudo docker compose run --rm --no-deps app python manage.py check_illustrations --name "toalhas"
```

Sem `--name`, o comando valida apenas os arquivos do catálogo; isso não garante que qualquer nome cadastrado tenha correspondência. Com `--name`, ele também mostra a ilustração reconhecida e retorna erro se o nome for desconhecido ou ambíguo. Nenhuma das opções altera presentes.

Após atualizar o código ou os aliases, reconstrua a imagem Docker e recrie o app conforme o guia de atualização em [DEPLOY-DOCKER-ORACLE.md](DEPLOY-DOCKER-ORACLE.md). Fora do Docker, reinicie os processos Django/Gunicorn: o catálogo e as correspondências ficam em cache por processo. `collectstatic` sozinho não atualiza essas regras.

Para presentes já cadastrados sem imagem, abra o painel, clique em **Usar ilustração** ou **Escolher ilustração**, confira a prévia e confirme. Novos cadastros com nomes reconhecidos ou escolha manual recebem a ilustração ao salvar. Migrations, inicialização e visitas públicas não aplicam imagens antigas em massa.

## Incluir novos objetos

Gere a arte **fora do site**, usando ChatGPT/Codex, e solicite atualização do catálogo por PR. Direção visual: objeto identificado pelo nome, centralizado e totalmente visível, fundo neutro claro, luz suave, sem pessoas, marcas, logotipos ou texto. Não envie URLs de rastreamento, credenciais ou dados de convidados. Represente conjuntos quando informados, sem inventar características técnicas.

Na preparação do código, revise a arte, valide/recodifique com `gifts.external.recode_image`, inclua WebP e entrada no manifesto com aliases específicos e SHA-256. Acrescente testes do nome e ambiguidades relevantes, rode as verificações e reconstrua ambos os targets Docker. Consulte os nomes reconhecidos na tabela abaixo e no manifesto. O script de reset separado não participa desse processo.

Atualizar uma fonte/hash não substitui automaticamente as cópias dos presentes. O gestor revisa a prévia por item e confirma a troca. Objetos ainda não cobertos continuam com o padrão até inclusão manual.

## Provedores considerados

Pesquisa em **20/10/2026**. A escolha final foi o catálogo local, aprovado após esclarecer a separação entre Plus e API. Não instalamos clientes OpenAI, fal.ai ou Pollinations nem variáveis de chave sem implementação.

- **OpenAI:** a ferramenta desta conversa gerou as imagens; isso não comprova uma integração de API no servidor. [Plus](https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus), [faturamento ChatGPT/API](https://help.openai.com/en/articles/9039756-billing-settings-in-chatgpt-vs-platform) e [preços](https://openai.com/api/pricing/) são referências; as páginas retornaram 403 de política nesta rede. Não publicamos preços/modelos atuais como se estivessem confirmados.
- **fal.ai / FLUX.1 [schnell]:** era a recomendação inicial, condicionada à verificação. [Modelo](https://fal.ai/models/fal-ai/flux/schnell) e [API](https://fal.ai/models/fal-ai/flux/schnell/api) foram bloqueados; preço, autenticação e parâmetros atuais não foram confirmados. Não foi integrado.
- **Pollinations:** a [documentação da branch padrão main](https://github.com/pollinations/pollinations/blob/main/APIDOCS.md), efetivamente lida, descreve Bearer e créditos Pollen. A [Classic na branch master](https://github.com/pollinations/pollinations/blob/master/APIDOCS.md) anuncia acesso anônimo limitado, uma imagem por vez, intervalo mínimo de 45 segundos, marca da plataforma e funcionamento sem garantia. É uma modalidade distinta, mantida para aplicações existentes; não é prova de API gratuita ilimitada para um novo site. O serviço também foi bloqueado nesta rede, sem teste real de geração por ele.

O catálogo entrega imagens reais geradas nesta conversa e operação local sem API de geração. Nenhum serviço pago foi integrado ou ativado.

## Objetos do catálogo

| Objeto | Exemplos de nome reconhecido |
| --- | --- |
| Talheres | faqueiro, talher, talheres, jogo de talher, kit de talher |
| Kit de toalhas | kit toalha, kit toalhas, toalhas, jogo de toalha |
| Pratos | prato, pratos, aparelho de jantar |
| Copos | copo, copos |
| Chaleira elétrica | chaleira eletrica |
| Liquidificador | liquidificador |
| Kit de panelas | panela, panelas, kit panelas, kit de panelas |
| Frigideira | frigideira |
| Leiteira | leiteira |
| Pipoqueira | pipoqueira, panela de pipoca |
| Kit de utensílios | kit utensilios, kit de utensilios |
| Kit de facas | kit facas, kit de facas |
| Refratário redondo com tampa | pirex redondo, refratario redondo |
| Refratário retangular | pirex retangular, refratario retangular |
| Forma de bolo | forma de bolo, forma bolo |
| Forma de pizza | forma de pizza, forma pizza |
| Saleiro | saleiro |
| Açucareiro | acucareiro |
| Tábua de corte | tabua de carne, tabua de corte |
| Panos de chão | panos de chao, pano de chao |
| Panos de prato | panos de prato, pano de prato |
| Prendedores de roupas | prendedor de roupas, prendedores de roupas |
| Baldes | balde, baldes |
| Pá de lixo | pa de lixo, pazinha de lixo |
| Rodinho de pia | rodinho de pia, rodo de pia |
| Cesto de roupas | cesto de roupas, cesto de roupa |
| Bacias | bacia, bacias |
| Potes de plástico | potes de plastico, potes plasticos |
| Potes herméticos para mantimentos | potes hermeticos, potes para mantimentos |
| Potes de vidro | potes de vidro, potes vidro |
| Pote para pipoca | pote grande para pipoca, pote para pipoca |
| Porta detergente | porta detergente |
| Jarra | jarra de suco, jarra para suco |
| Tesoura de cozinha | tesoura de cozinha |
| Escorredor de macarrão | escorredor de macarrao |
| Porta temperos | porta temperos, porta tempero |
| Potes de sobremesa | potes de sobremesa, pote de sobremesa |
| Porta sabonete | porta sabonete |
| Lixeira | lixeira |
| Jogo de roupa de cama | jogo roupa de cama, jogo de roupa de cama |
| Tapetes de banheiro | tapetes banheiro, tapetes de banheiro |
| Batedeira | batedeira |
| Cafeteira | cafeteira |
| Mini processador | mini processador, miniprocessador |
| Sanduicheira | sanduicheira |
| Ferro de passar | ferro de passar |
| Mini máquina de waffle | maquina de waffle, mini maquina de waffle |
| Par de Luvas Térmicas de Forno | luvas térmicas de forno, luvas de forno |
| Saca Rolhas | saca rolhas, saca-rolhas, sacarrolhas |
| Abridor de Garrafas | abridor de garrafa, abridores de garrafas |
| Abridor de Latas | abridor de lata, abridores de latas |
| Organizador de Armário (caixinhas) | organizador de armário, caixas organizadoras de armário |
| Cortador de Legumes | cortador de legumes, cortadores de legumes |
| Panela de Pressão | panela de pressão, panelas de pressão |
| Kit Vassoura/Rodo/Pá | kit vassoura/rodo/pá, kit de vassoura rodo e pá de lixo |
| Xícaras de Café Vidro Duplo | xícara de café vidro duplo, xícaras de café de parede dupla |
| Aspirador de Pó | aspirador de pó, aspiradores de pó |
| Esteira Escorredor de Louças | esteira escorredor de louças, tapete escorredor de louças |
| Escova Sanitária | escova sanitária, escovas sanitárias |
| Ralador Inox | ralador inox, ralador de aço inox |
| Cabides de Roupa | cabides de roupa, cabides |
| Air fryer | air fryer, airfryer, fritadeira sem óleo |
