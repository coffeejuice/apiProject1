REM @echo off && setlocal enabledelayedexpansion

SET "app_name=forgelabSimulation-2.0.16"
SET "root_dir=c:\"
SET "app_dir=%root_dir%%app_name%\"
SET "packages_dir=%app_dir%packages\"

CD %app_dir%
py -m venv .venv && timeout 10 && .venv\Scripts\activate && py -m pip install --no-index --find-links=%packages_dir% -r %app_dir%requirements_all_freeze.txt
