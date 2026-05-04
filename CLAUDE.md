# CLAUDE.md

Before doing anything:

1. Create a new conda env named "auto-dev"
2. Install all dependencies inside it
3. NEVER use system Python
4. Always run commands inside the env

If env exists, reuse it


- NEVER delete files not belong to this project
- NEVER use sudo
- NEVER modify system directories
- ALWAYS create backups before overwrite
- If unsure → STOP and explain


Success criteria:

1. All tests pass (pytest / npm test)
2. No lint errors
3. Project runs successfully
4. Code is modular and documented

When ALL conditions are satisfied:
Output EXACTLY:

<promise>COMPLETE</promise>