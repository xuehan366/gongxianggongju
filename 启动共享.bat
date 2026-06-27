@echo off
chcp 65001 >nul
title 局域网文件共享工具
cd /d "%~dp0"
pythonw lan_share.py
