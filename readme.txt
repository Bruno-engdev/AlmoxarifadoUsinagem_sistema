NOTA: O projeto está em uma unidade de rede (R:), que não suporta venv local.
O venv será criado em C: drive.

Para criar o ambiente virtual:
python -m venv C:\venvs\almox_usinagem --copies

Para ativar:
& C:\venvs\almox_usinagem\Scripts\Activate.ps1

Depois de ativado, instale as dependências:
pip install -r requirements.txt

OU, sem ativar, execute diretamente:
& C:\venvs\almox_usinagem\Scripts\python.exe -m pip install -r requirements.txt

Para desativar:
deactivate
