import logging
import os
from pyodm import Node

import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    n = Node('nodeodm-sunshaine.azurewebsites.net', 80)
    task = n.get_task(name)
    dir = os.path.join('/datashare/downloads/', name)
    task.download_assets(dir)
    logging.info('downloaded')
    if name:
        return func.HttpResponse("downloaded")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
