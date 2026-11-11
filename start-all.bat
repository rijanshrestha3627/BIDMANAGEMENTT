@echo off
title Start Auction System
echo ==========================================================
echo  Starting University Auction Bid Management System
echo ==========================================================

powershell.exe -ExecutionPolicy Bypass -File "%~dp0start-all.ps1"
pause
