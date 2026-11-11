@echo off
title Stop Auction System
echo Stopping University Auction Bid Management System...
powershell.exe -ExecutionPolicy Bypass -File "%~dp0stop-all.ps1"
pause
