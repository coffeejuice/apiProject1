@echo off && setlocal enabledelayedexpansion

set "_Key=HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
for /f tokens^=3 %%i in ('%__APPDIR__%reg.exe query "!_Key!"^|find/i "Personal"')do <con: call set "docs_dir=%%~i"

SET "app_name=forgelabSimulation"
SET "root_dir=c:\"
SET "app_dir=%root_dir%%app_name%\"
SET "sim_dir=%docs_dir%\forgelabProjects\"
SET "packages_dir=%app_dir%packages\"

cd %sim_dir%

FOR %%X IN (%app_name%*.zip) DO (
	SET "new_release=%%~nX"
)

IF NOT DEFINED new_release EXIT /b

CD %root_dir%
RMDIR /s /q %app_name%

"C:\Program Files\7-Zip\7z.exe" x "%sim_dir%%new_release%.zip"  -o%root_dir%

REN %new_release% %app_name%

CD %app_dir%
python run_as_service.py stop
pip install --no-index --find-links=%packages_dir% -r %app_dir%requirements.txt

python run_as_service.py start

REM DEL %sim_dir%%newRelease%.zip

ECHO. > %sim_dir%%newRelease%.txt

EXIT /b
