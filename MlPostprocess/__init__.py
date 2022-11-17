import logging

import azure.functions as func

import sys
import os
import cv2
import argparse
import json
import numpy as np
from osgeo import gdal, osr
import torch
from PIL import Image
# add local 'external components' path to sys.path for import
local_libs = os.getcwd()
sys.path.append(os.path.join(local_libs, "external"))


MOSAIC_META = "mosaics.json"
ANOMALY_META = "anomalies.json"
ORTHOPHOTO_PATTERN = '*.tif'
PATCH_SIZE_HEIGHT = 512
PATCH_SIZE_WIDTH = 640
PATCHES_FOLDER = 'patches'


def main(msg: func.QueueMessage, msgout: func.Out[func.QueueMessage]) -> None:
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))

    uuid = msg.get_body().decode('utf-8')

    dir = '/datashare/downloads/' + uuid + "/odm_orthophoto"

    orthophoto = os.path.join(dir, "odm_orthophoto.tif")

    num_anomalies = post_process(orthophoto)

    logging.info('Postprocessing done. num_anomalies=' + str(num_anomalies))
    msgout.set(uuid)


    



def lambda_handler(event, context):
    assert event['file_name'] is not None and len(event['file_name']) > 0, "Missing param 'file_name'!"
    num_anomalies = post_process(event['file_name'])
    return {
        "file_name": event['file_name'],
        "anomalies": num_anomalies,
    }


def compute_colors_for_labels(labels, palette=None):
    """
    Simple function that adds fixed colors depending on the class
    """
    if palette is None:
        palette = torch.tensor([2 ** 25 - 1, 2 ** 15 - 1, 2 ** 21 - 1])
    colors = labels[:, None] * palette
    colors = (colors % 255).numpy().astype("uint8")
    return colors


def load_meta_data(folder, meta_fn):
    meta_fn = os.path.join(folder, meta_fn)
    meta = None
    if os.path.exists(meta_fn):
        with open(meta_fn, "r") as f:
            meta = json.load(f)
    return meta


def merge_anomalies(mosaic_meta, anomalie_meta):
    boxes, classes, scores, contours, centers = [], [], [], [], []
    for mosaic in mosaic_meta:
        for patch in mosaic_meta[mosaic]:
            if patch['patch_name'] in anomalie_meta:
                a = anomalie_meta[patch['patch_name']]
                # map patch coordinates into mosaic coordinates
                for box in a['boxes']:
                    box[0] += patch['x']
                    box[1] += patch['y']
                    box[2] += patch['x']
                    box[3] += patch['y']
                for contour in a['contours']:
                    c = contour[0]
                    for p in c:
                        p[0][0] += patch['x']
                        p[0][1] += patch['y']
                for center in a['centers']:
                    center[0] += patch['x']
                    center[1] += patch['y']
                boxes += a['boxes']
                classes += a['classes']
                scores += a['scores']
                contours += a['contours']
                centers += a['centers']

    anomalies = {
        'boxes': boxes,
        'classes': classes,
        'scores': scores,
        'contours': contours,
        'centers': centers,
    }
    return anomalies


def save_anomalies(folder, anomalies):
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return json.JSONEncoder.default(self, obj)

    with open(os.path.join(folder, ANOMALY_META), 'w') as m:
        m.write(json.dumps(anomalies, indent=4, cls=NumpyEncoder))


def mark_anomalies(image_name, anomalies):
    image = Image.open(image_name).convert('RGB')
    image = np.array(image)

    scores = anomalies['scores']
    boxes = torch.IntTensor(anomalies['boxes'])
    contours = anomalies["contours"]
    labels = torch.IntTensor(anomalies["classes"])
    centers = anomalies["centers"]

    colors = compute_colors_for_labels(labels).tolist()

    for nr, (contour, color, box, score, label, center) in enumerate(zip(contours, colors, boxes, scores, labels, centers)):
        original = image.copy()

        if len(contour) == 1:

            contour1 = np.array(contour)

            # add mask to image with transparent overlay
            # overlay = cv2.fillPoly(image, contour1, color)
            # alpha = 0.2
            # image = cv2.addWeighted(overlay, alpha, original, 1 - alpha, 0)
            # draw contour around mask
            border = cv2.drawContours(image, contour1, -1, (255, 255, 0), 1)
            alpha = 0.8
            image = cv2.addWeighted(border, alpha, original, 1 - alpha, 0)

            # box = box.to(torch.int64)
            # top_left, bottom_right = box[:2].tolist(), box[2:].tolist()
            # image = cv2.rectangle(
            #     image, tuple(top_left), tuple(bottom_right), tuple(color), 1
            # )

            # add bounding box
            x, y, w, h = cv2.boundingRect(contour1[0])
            # cv2.rectangle(image, (x, y), (x + w, y + h), color, 1)

            # add class label and probability
            s = f"{nr} ({label}: {score:.2f})"
            # x, y = box[:2]
            cv2.putText(image, s, (int(x) - 2, int(y) - 2), cv2.FONT_HERSHEY_SIMPLEX, .3, (255, 255, 255), 1)

            # add centers
            cv2.circle(image, center, radius=1, color=(255, 0, 0), thickness=-1)

    result = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    image_folder, image_fn = os.path.split(image_name)
    cv2.imwrite(os.path.join(image_folder, image_fn + '-result.jpg'), result)
    print("")


def add_gps_coords(file_name, anomalies):

    def get_coord_transform_gps():
        # get the existing coordinate system
        old_cs = osr.SpatialReference()
        old_cs.ImportFromWkt(tif.GetProjectionRef())

        # create the new coordinate system (WGS84)
        wgs84_wkt = """
        GEOGCS["WGS 84",
            DATUM["WGS_1984",
                SPHEROID["WGS 84",6378137,298.257223563,
                    AUTHORITY["EPSG","7030"]],
                AUTHORITY["EPSG","6326"]],
            PRIMEM["Greenwich",0,
                AUTHORITY["EPSG","8901"]],
            UNIT["degree",0.01745329251994328,
                AUTHORITY["EPSG","9122"]],
            AUTHORITY["EPSG","4326"]]"""
        new_cs = osr.SpatialReference()
        new_cs.ImportFromWkt(wgs84_wkt)

        # create a transform object to convert between coordinate systems
        transform = osr.CoordinateTransformation(old_cs, new_cs)
        return transform

    def pixel_to_coord(gt, p):
        # coefficients from geo transform of GeoTIFF
        x_min, x_size = gt[0], gt[1]
        y_min, y_size = gt[3], gt[5]
        # coord in map units, convert to world coord
        px = p[0] * x_size + x_min  # x pixel
        py = p[1] * y_size + y_min  # y pixel
        return [px, py]

    tif = gdal.Open(file_name)
    gt = tif.GetGeoTransform()
    transform = get_coord_transform_gps()

    latlongs = []
    for center in anomalies['centers']:
        pixel = pixel_to_coord(gt, center)
        latlong = transform.TransformPoint(pixel[0], pixel[1])
        latlongs.append(latlong)

    if len(latlongs) > 0:
        anomalies['latlong'] = latlongs

    return anomalies


def post_process(file_name):
    folder, name = os.path.split(file_name)
    mosaic_meta = load_meta_data(folder, MOSAIC_META)
    anomaly_meta = load_meta_data(os.path.join(folder, PATCHES_FOLDER), ANOMALY_META)
    anomalies = merge_anomalies(mosaic_meta, anomaly_meta)
    anomalies = add_gps_coords(file_name, anomalies)
    save_anomalies(folder, anomalies)
    mark_anomalies(file_name, anomalies)
    return len(anomalies['classes'])
