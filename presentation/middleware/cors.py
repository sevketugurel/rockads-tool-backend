from fastapi.middleware.cors import CORSMiddleware


def add_cors_middleware(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:4173",
            "http://localhost:5174",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:4173",
            "http://127.0.0.1:5174",
            "https://localhost:3000",
            "https://localhost:5173",
            "https://localhost:4173",
            "https://localhost:5174"
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )