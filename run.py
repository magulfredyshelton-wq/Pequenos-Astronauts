import uvicorn

from app.config import HOST, PORTA


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORTA, proxy_headers=True,
                forwarded_allow_ips="127.0.0.1")
