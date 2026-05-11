@echo off
echo Iniciando Automacao Flow - Gerador de Conteudo...
echo.

:: 1. Entre na pasta raiz do seu projeto
cd /d "%~dp0"

:: 2. Pega a ultima versao do repositorio
git pull

:: 3. Cria o venv se nao existir
if not exist "venv\Scripts\activate.bat" (
    echo Criando ambiente virtual...
    python -m venv venv
)

:: 4. Ativa o ambiente virtual
call venv\Scripts\activate

:: 5. Instala/atualiza dependencias
pip install --upgrade pip
pip install -r requirements.txt

:: 6. Executa o script principal
python main.py

:: 7. Mantem a janela aberta caso de algum erro
pause