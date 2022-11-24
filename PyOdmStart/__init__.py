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
    
    dir = os.path.join('/datashare/', name)
    files = os.listdir(dir)
    files = [os.path.join(dir, f) for f in files]

    logging.info("Files loaded: %s" % len(files))

    n = Node('nodeodm-sunshaine.azurewebsites.net', 80)

    task = n.create_task(files, options = {
        'dsm' : True,
        'orthophoto-resolution' : 1,
        'skip-3dmodel' : True,
        'resize-to' : -1,
        'min-num-features' : 25000,
        'orthophoto-cutline' : False,
        'pc-quality' : 'ultra',
        'mesh-size' : 600000,
        'feature-quality' : 'ultra',
        'depthmap-resolution' : 2000,
        'dem-resolution' : 1,
        'gps-accuracy' : 3,
        'mesh-octree-depth' : 13,
        'auto-boundary' : True,
        'radiometric-calibration' : "camera"
    }, name=name)

    logging.info("Task created with uuid: %s" % task.info().uuid)

    if name:
        return func.HttpResponse(task.info().uuid)
    else:
        return func.HttpResponse(
             "No foldername provided",
             status_code=200
        )