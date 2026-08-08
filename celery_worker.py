from app import create_app
from app.extensions import celery_app

app = create_app()
app.app_context().push()

if __name__ == "__main__":
    celery_app.start()
