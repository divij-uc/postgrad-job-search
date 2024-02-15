from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Annotated

from search import search, get_job_listings

import uuid
import pandas as pd
import os
import itertools

app = FastAPI()

templates = Jinja2Templates(directory="templates")


@app.get("/out/{file_name}", response_class=FileResponse)
async def download_file(file_name):
    return FileResponse(f"out/{file_name}.csv")


@app.get("/")
async def start_redirect():
    return RedirectResponse(url="/search")


@app.get("/search/")
async def start(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"wsurl": os.environ["WSURL"]}
    )


def valid_df(input_link: str):
    df = pd.read_csv(input_link)
    print(input_link)
    try:
        assert "Company" in df.columns
        assert "URL" in df.columns
        assert "Keywords" in df.columns
        assert "Exclude" in df.columns
        return df
    except:
        return None


@app.get("/out/{file_path}")
async def download_file(file_path):
    FileResponse(file_path)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        input_link = await websocket.receive_text()
        if input_link == "https://secret":
            input_link = os.environ["CONFIGCSV"]
        res = valid_df(input_link)
        if res is not None:
            break
        m = """
        <div class="alert alert-danger">
            Check the columns at the link you entered!
        </div>
        """
        await websocket.send_text(m)

    await websocket.send_text(f"Found the sheet, starting scraping now!")

    full_job_listings = await search(res)

    if full_job_listings.shape[0] == 0:
        await websocket.send_text(f"None Found!")
    else:
        file_name = uuid.uuid4()
        file_path = f"out/{file_name}.csv"
        full_job_listings = full_job_listings.sort_values(by=["Company", "Title"])
        full_job_listings.to_csv(file_path, index=False)

        await websocket.send_text(
            f"""
        <div class="mb-3">
            <a href="../out/{file_name}" download="jobs.csv" class="btn btn-primary">Download table</a>
        </div>"""
        )

        job_listings_html = full_job_listings.to_html(
            index=False,
            render_links=True,
            classes="table table-striped w-25",
            justify="left",
            col_space="100px",
        )
        job_listings_html = (
            f'<div class="table table-responsive">{job_listings_html}</div>'
        )
        await websocket.send_text(job_listings_html)

        print(f"complete {full_job_listings.shape[0]}")
