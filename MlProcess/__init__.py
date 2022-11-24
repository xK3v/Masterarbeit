import logging

import azure.functions as func

import argparse
import sys
import os
import fnmatch
from PIL import Image
import json

# add local 'external components' path to sys.path for import
local_libs = os.getcwd()
sys.path.append(os.path.join(local_libs, "external"))

import albumentations as A
import albumentations.pytorch.transforms as PA
import torch
#import myutils
import cv2
import numpy as np

PATCHES_FOLDER = 'patches'
ANOMALY_META = "anomalies.json"
FILE_PATTERN = "*.png"

def main(msg: func.QueueMessage, msgout: func.Out[func.QueueMessage]) -> None:
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))

    uuid = msg.get_body().decode('utf-8')

    dir = os.path.join('/datashare/downloads', uuid, 'odm_orthophoto')


    model_name = os.path.join("/datashare/model", "sunshaine.model")
    num_patches = detect(os.path.join(dir, PATCHES_FOLDER), model_name, 0.75)


    logging.info('Processing done. num_patches=' + str(num_patches))
    msgout.set(uuid)


def get_cuda_device():
    if torch.cuda.is_available():
        print(f'GPU: {torch.cuda.get_device_name(0)}')
        device = torch.device('cuda')
        torch.cuda.empty_cache()
    else:
        device = torch.device('cpu')
    print(f'Device: {device}')
    return device


def center_from_contours(contours):
    centers = []
    for contour in contours:
        c = max(contour, key=len)
        M = cv2.moments(c)
        print(M)
        cx = int(M['m10'] / M['m00'])
        cy = int(M['m01'] / M['m00'])
        centers.append((cx, cy))
    return centers


def masks_to_contour(masks):
    contours = []
    masks = masks.ge(0.5).mul(255).byte().cpu().numpy()
    for mask in masks:
        ret, thresh = cv2.threshold(mask[0], 127, 255, 0)
        c, h = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours.append(c)
    return contours


def detect(folder, model_name, confidentiality=0.5):

    model = torch.load(model_name, map_location=torch.device('cpu'))
    model.eval()

    device = get_cuda_device()
    model.to(device)

    # --------------------

    transforms = A.Compose([
        A.ToGray(p=1),
        A.ToFloat(max_value=255),
        PA.ToTensorV2(),
    ])

    image_files = [name for name in os.listdir(folder)
                   if os.path.isfile(os.path.join(folder, name))
                   and fnmatch.fnmatch(name, FILE_PATTERN)]

    anomalies = {}

    for image_fn in image_files:

        print(f"Processing file {image_fn}...")

        img = Image.open(os.path.join(folder, image_fn)).convert('RGB')

        i = transforms(image=np.array(img))['image']
        if device.type == 'cuda':
            i = i.cuda()

        with torch.no_grad():
            predictions = model([i])

        if len(predictions) > 0 and len(predictions[0]['scores'].detach().cpu().tolist()) > 0:
            p = predictions[0]
            idx = p['scores'].detach().cpu().numpy() > confidentiality
            scores = p['scores'].detach().cpu().numpy()[idx]
            if len(scores) > 0:
                classes = p['labels'].detach().cpu().numpy()[idx]
                boxes = p['boxes'].byte().detach().cpu().numpy()[idx]
                contours = masks_to_contour(p['masks'][idx])
                centers = center_from_contours(contours)
                anomalies[image_fn] = {
                    'boxes': boxes,
                    'classes': classes,
                    'scores': scores,
                    'contours': contours,
                    'centers': centers,
                }
    save_anomalies(folder, anomalies)

    return len(anomalies.keys())


def save_anomalies(folder, anomalies):
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return json.JSONEncoder.default(self, obj)

    with open(os.path.join(folder, ANOMALY_META), 'w') as m:
        m.write(json.dumps(anomalies, indent=4, cls=NumpyEncoder))


def lambda_handler(event, context):
    assert event['file_name'] is not None and len(event['file_name']) > 0, "Missing param 'file_name'!"
    #assert event['model_name'] is not None and len(event['model_name']) > 0, "Missing param 'model_name'!"
    #assert event['confidentiality'] is not None and len(event['confidentiality']) > 0, "Missing param 'confidentiality'!"
    folder, name = os.path.split(event['file_name'])
    model_name = os.path.join("/mnt/sunshaine/model", "sunshaine.model")
    num_patches = detect(os.path.join(folder, PATCHES_FOLDER), model_name, 0.75)
    return {
        "file_name": event['file_name'],
        "patches": num_patches
    }

