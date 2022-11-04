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
    
    dir = '/datashare/Fotos_3/W'
    files = os.listdir(dir)
    files = [os.path.join(dir, f) for f in files]

    n = Node('nodeodm-sunshaine.azurewebsites.net', 80)
    task = n.create_task(files, name=name, options=
        {
            "auto-boundary": True,
            "dem-resolution": 3,
            "depthmap_resolution": 1280,
            "dsm": True,
            "feature-quality": "ultra",
            "gps-accuracy": 3,
            "mesh-octree-depth": 12,
            "mesh-size": 400000,
            "min-num-features": 15000,
            "orthophoto-cutline": True,
            "orthophoto-resolution": 3,
            "pc-quality": "ultra",
            "resize-to": -1,
            "skip-3dmodel": True
        })
    #task.wait_for_completion()
    #task.download_results()

    if name:
        #return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
        #return func.HttpResponse("Task created with name: %s" % task.info.name)
        return func.HttpResponse(task.info().uuid)
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )