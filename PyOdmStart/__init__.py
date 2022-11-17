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
    
    dir = '/datashare/Fotos_3/T'
    files = os.listdir(dir)
    files = [os.path.join(dir, f) for f in files]

    logging.info("Files loaded: %s" % len(files))

    n = Node('nodeodm-sunshaine.azurewebsites.net', 80)

    task = n.create_task(files, options = {
        #'dsm' : True,
        #'orthophoto-resolution' : 3,
        'skip-3dmodel' : True,
        #'force-gps' : True,
        #'ignore-gsd' : True,
        #'resize-to' : -1,

        #'pc-csv' : True,
        #'min-num-features' : 15000,
        #'orthophoto-cutline' : True,
        #'pc-quality' : 'ultra',
        #'mesh-size' : 400000,
        #'texturing-skip-global-seam-leveling' : True,
        #'feature-quality' : 'ultra',
        #'depthmap-resolution' : 1280,
        #'dem-resolution' : 3,
        #'gps-accuracy' : 3,
        #'mesh-octree-depth' : 12,
        #'auto-boundary' : True
    }, name=name)

    #task.wait_for_completion()
    #task.download_results()

    logging.info("Task created with uuid: %s" % task.info().uuid)

    if name:
        #return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
        #return func.HttpResponse("Task created with name: %s" % task.info.name)
        return func.HttpResponse(task.info().uuid)
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )