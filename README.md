# BotSHORT - Gerador Automático de Vídeos Curtos

Este projeto é uma aplicação web feita em Python (Flask) que gera vídeos curtos automaticamente. Ele utiliza inteligência artificial para criar roteiros (Google Gemini), gera narração (Edge TTS), cria imagens ilustrativas (Pollinations.ai) e junta tudo em um vídeo pronto para redes sociais usando o MoviePy.

## Pré-requisitos

Certifique-se de ter instalado em sua máquina:
- [Python 3.8+](https://www.python.org/downloads/)
- Uma chave de API válida do [Google Gemini (Google AI Studio)](https://aistudio.google.com/)

## Como configurar e rodar o projeto

### 1. Clonar o repositório
```bash
git clone https://github.com/feneto7/botSHORT.git
cd botSHORT
```

### 2. Criar e ativar um ambiente virtual (Recomendado)
No Windows:
```bash
python -m venv venv
venv\Scripts\activate
```
No Linux/Mac:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar as dependências
Com o ambiente virtual ativado, instale as bibliotecas necessárias que estão no arquivo `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Configurar as variáveis de ambiente
Crie um arquivo chamado `.env` na raiz do projeto (na mesma pasta de `app.py`). 
Dentro dele, adicione a sua chave da API do Gemini da seguinte forma:

```env
GEMINI_API_KEY=sua_chave_de_api_aqui
```

### 5. Executar a aplicação
Para iniciar o servidor, execute o seguinte comando no terminal:
```bash
python app.py
```

O servidor será iniciado localmente. Acesse a aplicação abrindo o navegador no endereço:
[http://127.0.0.1:5000](http://127.0.0.1:5000) ou [http://localhost:5000](http://localhost:5000)

## Estrutura do Projeto
- `app.py`: Arquivo principal da aplicação (Servidor Flask e lógica de geração do vídeo).
- `requirements.txt`: Lista de dependências do projeto.
- `.env`: Arquivo de configuração local (deve ser criado por você, onde fica sua chave de API).
- `templates/`: Pasta contendo a interface web em HTML (`index.html`).
- `static/output/`: Pasta onde os vídeos finais gerados serão salvos.
- `temp/`: Pasta temporária usada para manipular o áudio e as imagens durante a geração do vídeo.
