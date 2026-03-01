from fastapi import FastAPI
from fastapi_crons import Crons

app = FastAPI()
crons = Crons(app)
