from fastapi import FastAPI
from api.routes import router

def create_app() -> FastAPI:
    """
    Application factory to initialize the FastAPI instance
    and wire up all the modular routing.
    """
    app = FastAPI(
        title="YouTube Downloader",
        description="A robust, modular API for downloading videos.",
        version="1.0.0"
    )

    # Include the endpoint mappings from our routes module
    app.include_router(router)
    
    return app

# The final callable application object expected by Uvicorn
app = create_app()