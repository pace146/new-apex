@echo off
title APEX ONE-CLICK RUNNER
echo ==========================================================
echo              A P E X   O N E - C L I C K   R U N N E R
echo ==========================================================

set ZIP_DIR=input_zips
set ZIP_FILE=

for %%f in (%ZIP_DIR%\*.zip) do (
    set ZIP_FILE=%%f
    goto zipFound
)

:zipFound

if "%ZIP_FILE%"=="" (
    echo ❌ No ZIP file found in input_zips folder.
    pause
    exit /b
)

echo Found ZIP: %ZIP_FILE%
echo.

echo [1/7] Extracting XML...
python apex_xml_extractor.py --zip "%ZIP_FILE%"
if %errorlevel% neq 0 goto ERR

echo [2/7] Running CPR cleaner...
python apex_cleaner_v2.7.py
if %errorlevel% neq 0 goto ERR

echo [3/7] Integrating Live Odds...
python apex_live_odds_integrator_pp.py --live live_odds.csv
if %errorlevel% neq 0 goto ERR

echo [4/7] Running Monte Carlo...
python apex_montecarlo_v1.py
if %errorlevel% neq 0 goto ERR

echo [5/7] Building MC vertical tickets...
python verticals_mc_builder_v1_3.py
if %errorlevel% neq 0 goto ERR

echo [6/7] Building Horizontal Tickets...
python apex_horizontal_bankroll_v1_3.py
if %errorlevel% neq 0 goto ERR

echo [7/7] Building UTF Bet Slips...
python utf_builder_v1_7.py
if %errorlevel% neq 0 goto ERR

echo ==========================================================
echo              PROCESS COMPLETE — CHECK UTF_Output
echo ==========================================================
pause
exit /b

:ERR
echo.
echo ❌ APEX PIPELINE FAILED — CHECK ERROR ABOVE
pause
exit /b
