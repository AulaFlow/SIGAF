# api

API de SIGAF con FastAPI.

```bash
cd api
pip install -r requirements-dev.txt
uvicorn app.main:app --reload   # http://localhost:8000/health
ruff check . && bandit -r app -c pyproject.toml && pytest   # cobertura mínima 60 %
```
