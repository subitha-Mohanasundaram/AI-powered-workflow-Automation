@echo off
del /f /q "C:\AI-powered workflow Automation\.git\index.lock" 2>nul
cd /d "C:\AI-powered workflow Automation"
git add -A
git commit -m "Phase 1+2+3: JWT auth, custom execution engine, plugin system, SSE monitoring, React frontend, Alembic, workflow CRUD v1"
git push origin main
echo Done.
pause
