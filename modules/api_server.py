from fastapi import FastAPI


app = FastAPI(title="Competitor Intelligence System")


@app.get("/")
def health_check():
    return {"status": "ok"}
