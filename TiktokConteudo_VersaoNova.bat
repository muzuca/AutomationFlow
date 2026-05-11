@echo off
echo Iniciando Automacao Flow - Gerador de Conteudo...
echo.

:: 1. Entre na pasta raiz do seu projeto
cd /d "C:\Users\vinic\Desktop\Projetos\AutomationFlow"

:: 2. Pega a ultima versao do repositorio
git pull

:: 3. Ative o ambiente virtual (supondo que o nome da pasta do seu venv seja 'venv')
:: Se o nome for diferente, troque 'venv' pelo nome correto (ex: 'ambiente_instancia_1')
call venv\Scripts\activate

:: 4. Instala os ultimos pacotes necessarios
pip install --upgrade pip
pip install -r .\requirements.txt

:: 3. Execute o script principal
python main.py

:: 4. Mantém a janela aberta caso dê algum erro (opcional, mas recomendado)
pause