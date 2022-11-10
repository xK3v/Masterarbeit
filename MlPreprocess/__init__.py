import logging

import azure.functions as func

import fnmatch
import os
import cv2
import argparse
import json
import shutil

MOSAIC_META = "mosaics.json"
ORTHOPHOTO_PATTERN = '*.tif'
PATCH_SIZE_HEIGHT = 512
PATCH_SIZE_WIDTH = 640
PATCHES_FOLDER = 'patches'


def main(msg: func.QueueMessage, msgout: func.Out[func.QueueMessage]) -> None:
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))
    uuid = msg.get_body().decode('utf-8')

    dir = '/datashare/downloads/' + uuid + "/odm_orthophoto"
    orthophotos = os.listdir(dir)
    orthophotos = [f for f in orthophotos if fnmatch.fnmatch(f, ORTHOPHOTO_PATTERN)]
    if len(orthophotos) > 0:
        split_orthophotos(dir, orthophotos)
    
    logging.info('Preprocessing done')
    msgout.set(uuid)
    



def cleanup_folder(folder):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))


def split_orthophoto(file_name):

    image = cv2.imread(file_name)
    height, width, channels = image.shape

    pad_h = height - PATCH_SIZE_HEIGHT * (height // PATCH_SIZE_HEIGHT)
    pad_w = width - PATCH_SIZE_WIDTH * (width // PATCH_SIZE_WIDTH)

    # first pad image to multiples of PATCH_SIZE_WIDTHxPATCH_SIZE_HEIGHT
    padded = cv2.copyMakeBorder(image, 0, pad_h, 0, pad_w, cv2.BORDER_CONSTANT, 0)
    padded_height, padded_width, padded_channels = padded.shape

    # cv2.imwrite(f'{file_name}-padded.tif', padded)

    mosaic_data = []

    x = y = 0
    h, w = PATCH_SIZE_HEIGHT, PATCH_SIZE_WIDTH
    i = 0

    while y+h <= padded_height:
        while x+w <= padded_width:
            p = padded[y:y+h, x:x+w]
            i += 1
            patch_name = f'{file_name}-patch{i}.png'
            folder, name = os.path.split(patch_name)
            patch_name = os.path.join(folder, PATCHES_FOLDER, name)
            cv2.imwrite(patch_name, p)
            mosaic_data.append({
                "patch_name": f'{name}',
                "x": x,
                "y": y,
            })
            x += w
        x = 0
        y += h

    return mosaic_data


def split_orthophotos(folder, file_names):
    def init_patches_folder(folder):
        patches_folder = f'{folder}/{PATCHES_FOLDER}'
        if not os.path.exists(patches_folder):
            os.makedirs(patches_folder)
        else:
            cleanup_folder(patches_folder)
    init_patches_folder(folder)
    mosaics_meta = {}
    for file_name in file_names:
        mosaics_meta[file_name] = split_orthophoto(os.path.join(folder, file_name))
    with open(os.path.join(folder, MOSAIC_META), 'w') as m:
        m.write(json.dumps(mosaics_meta, indent=4))
    # return amount of files processed
    return mosaics_meta


def lambda_handler(event, context):
    assert event['file_name'] is not None and len(event['file_name']) > 0, "Missing param 'file_name'!"
    folder, name = os.path.split(event['file_name'])
    patches = split_orthophotos(folder, [name])
    num_patches = 0
    if name in patches:
        num_patches = len(patches[name])
    return {
        "file_name": event['file_name'],
        "patches": num_patches
    }