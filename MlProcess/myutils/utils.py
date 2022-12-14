import torchvision.transforms
from torchvision.models.detection import mask_rcnn
import torch
import numpy as np
import matplotlib.pyplot as plt
import cv2


def select_top_predictions(predictions, threshold):
    idx = (predictions["scores"] > threshold).nonzero().squeeze(1)
    new_predictions = {}
    for k, v in predictions.items():
        new_predictions[k] = v[idx]
    return new_predictions


def compute_colors_for_labels(labels, palette=None):
    """
    Simple function that adds fixed colors depending on the class
    """
    if palette is None:
        palette = torch.tensor([2 ** 25 - 1, 2 ** 15 - 1, 2 ** 21 - 1])
    colors = labels[:, None] * palette
    colors = (colors % 255).numpy().astype("uint8")
    return colors


def overlay_boxes(image, predictions):
    """
    Adds the predicted boxes on top of the image
    Arguments:
        image (np.ndarray): an image as returned by OpenCV
        predictions (BoxList): the result of the computation by the model.
            It should contain the field `labels`.
    """
    labels = predictions["labels"]
    boxes = predictions['boxes']

    colors = compute_colors_for_labels(labels).tolist()

    for box, color in zip(boxes, colors):
        box = box.to(torch.int64)
        top_left, bottom_right = box[:2].tolist(), box[2:].tolist()
        image = cv2.rectangle(
            image, tuple(top_left), tuple(bottom_right), tuple(color), 1
        )

    return image


def overlay_mask(image, predictions):
    """
    Adds the instances contours for each predicted object.
    Each label has a different color.
    Arguments:
        image (np.ndarray): an image as returned by OpenCV
        predictions (BoxList): the result of the computation by the model.
            It should contain the field `mask` and `labels`.
    """
    masks = predictions["masks"].ge(0.5).mul(255).byte().numpy()
    labels = predictions["labels"]

    colors = compute_colors_for_labels(labels).tolist()

    for mask, color in zip(masks, colors):
        thresh = mask[0, :, :, None]
        contours, hierarchy = cv2.findContours(
            thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )
        # add mask to image
        original = image.copy()
        overlay = cv2.fillPoly(image, contours, color)
        alpha = 0.2
        image = cv2.addWeighted(overlay, alpha, original, 1 - alpha, 0)
        # add contour to image
        border = cv2.drawContours(image, contours, -1, (30, 255, 255), 1)
        alpha = 0.8
        image = cv2.addWeighted(border, alpha, original, 1 - alpha, 0)

    composite = image

    return composite


def overlay_keypoints(image, predictions):
    kps = predictions["keypoints"]
    scores = predictions["keypoints_scores"]
    kps = torch.cat((kps[:, :, 0:2], scores[:, :, None]), dim=2).numpy()
    for region in kps:
        image = vis_keypoints(image, region.transpose((1, 0)))
    return image


def vis_keypoints(img, kps, kp_thresh=2, alpha=0.7):
    """Visualizes keypoints (adapted from vis_one_image).
    kps has shape (4, #keypoints) where 4 rows are (x, y, logit, prob).
    """
    dataset_keypoints = PersonKeypoints.NAMES
    kp_lines = PersonKeypoints.CONNECTIONS

    # Convert from plt 0-1 RGBA colors to 0-255 BGR colors for opencv.
    cmap = plt.get_cmap('rainbow')
    colors = [cmap(i) for i in np.linspace(0, 1, len(kp_lines) + 2)]
    colors = [(c[2] * 255, c[1] * 255, c[0] * 255) for c in colors]

    # Perform the drawing on a copy of the image, to allow for blending.
    kp_mask = np.copy(img)

    # Draw mid shoulder / mid hip first for better visualization.
    mid_shoulder = (
                           kps[:2, dataset_keypoints.index('right_shoulder')] +
                           kps[:2, dataset_keypoints.index('left_shoulder')]) / 2.0
    sc_mid_shoulder = np.minimum(
        kps[2, dataset_keypoints.index('right_shoulder')],
        kps[2, dataset_keypoints.index('left_shoulder')])
    mid_hip = (
                      kps[:2, dataset_keypoints.index('right_hip')] +
                      kps[:2, dataset_keypoints.index('left_hip')]) / 2.0
    sc_mid_hip = np.minimum(
        kps[2, dataset_keypoints.index('right_hip')],
        kps[2, dataset_keypoints.index('left_hip')])
    nose_idx = dataset_keypoints.index('nose')
    if sc_mid_shoulder > kp_thresh and kps[2, nose_idx] > kp_thresh:
        cv2.line(
            kp_mask, tuple(mid_shoulder), tuple(kps[:2, nose_idx]),
            color=colors[len(kp_lines)], thickness=2, lineType=cv2.LINE_AA)
    if sc_mid_shoulder > kp_thresh and sc_mid_hip > kp_thresh:
        cv2.line(
            kp_mask, tuple(mid_shoulder), tuple(mid_hip),
            color=colors[len(kp_lines) + 1], thickness=2, lineType=cv2.LINE_AA)

    # Draw the keypoints.
    for l in range(len(kp_lines)):
        i1 = kp_lines[l][0]
        i2 = kp_lines[l][1]
        p1 = kps[0, i1], kps[1, i1]
        p2 = kps[0, i2], kps[1, i2]
        if kps[2, i1] > kp_thresh and kps[2, i2] > kp_thresh:
            cv2.line(
                kp_mask, p1, p2,
                color=colors[l], thickness=2, lineType=cv2.LINE_AA)
        if kps[2, i1] > kp_thresh:
            cv2.circle(
                kp_mask, p1,
                radius=3, color=colors[l], thickness=-1, lineType=cv2.LINE_AA)
        if kps[2, i2] > kp_thresh:
            cv2.circle(
                kp_mask, p2,
                radius=3, color=colors[l], thickness=-1, lineType=cv2.LINE_AA)

    # Blend the keypoints.
    return cv2.addWeighted(img, 1.0 - alpha, kp_mask, alpha, 0)


CATEGORIES = """BACKGROUND
person
bicycle
car
motorcycle
airplane
bus
train
truck
boat
traffic light
fire hydrant
N/A
stop sign
parking meter
bench
bird
cat
dog
horse
sheep
cow
elephant
bear
zebra
giraffe
N/A
backpack
umbrella
N/A
N/A
handbag
tie
suitcase
frisbee
skis
snowboard
sports ball
kite
baseball bat
baseball glove
skateboard
surfboard
tennis racket
bottle
N/A
wine glass
cup
fork
knife
spoon
bowl
banana
apple
sandwich
orange
broccoli
carrot
hot dog
pizza
donut
cake
chair
couch
potted plant
bed
N/A
dining table
N/A
N/A
toilet
N/A
tv
laptop
mouse
remote
keyboard
cell phone
microwave
oven
toaster
sink
refrigerator
N/A
book
clock
vase
scissors
teddy bear
hair drier
toothbrush
""".split("\n")


class PersonKeypoints(object):
    NAMES = [
        'nose',
        'left_eye',
        'right_eye',
        'left_ear',
        'right_ear',
        'left_shoulder',
        'right_shoulder',
        'left_elbow',
        'right_elbow',
        'left_wrist',
        'right_wrist',
        'left_hip',
        'right_hip',
        'left_knee',
        'right_knee',
        'left_ankle',
        'right_ankle'
    ]
    FLIP_MAP = {
        'left_eye': 'right_eye',
        'left_ear': 'right_ear',
        'left_shoulder': 'right_shoulder',
        'left_elbow': 'right_elbow',
        'left_wrist': 'right_wrist',
        'left_hip': 'right_hip',
        'left_knee': 'right_knee',
        'left_ankle': 'right_ankle'
    }


def kp_connections(keypoints):
    kp_lines = [
        [keypoints.index('left_eye'), keypoints.index('right_eye')],
        [keypoints.index('left_eye'), keypoints.index('nose')],
        [keypoints.index('right_eye'), keypoints.index('nose')],
        [keypoints.index('right_eye'), keypoints.index('right_ear')],
        [keypoints.index('left_eye'), keypoints.index('left_ear')],
        [keypoints.index('right_shoulder'), keypoints.index('right_elbow')],
        [keypoints.index('right_elbow'), keypoints.index('right_wrist')],
        [keypoints.index('left_shoulder'), keypoints.index('left_elbow')],
        [keypoints.index('left_elbow'), keypoints.index('left_wrist')],
        [keypoints.index('right_hip'), keypoints.index('right_knee')],
        [keypoints.index('right_knee'), keypoints.index('right_ankle')],
        [keypoints.index('left_hip'), keypoints.index('left_knee')],
        [keypoints.index('left_knee'), keypoints.index('left_ankle')],
        [keypoints.index('right_shoulder'), keypoints.index('left_shoulder')],
        [keypoints.index('right_hip'), keypoints.index('left_hip')],
    ]
    return kp_lines


PersonKeypoints.CONNECTIONS = kp_connections(PersonKeypoints.NAMES)


def overlay_class_names(image, predictions):
    """
    Adds detected class names and scores in the positions defined by the
    top-left corner of the predicted bounding box
    Arguments:
        image (np.ndarray): an image as returned by OpenCV
        predictions (BoxList): the result of the computation by the model.
            It should contain the field `scores` and `labels`.
    """
    scores = predictions["scores"].tolist()
    labels = predictions["labels"].tolist()
    #labels = [CATEGORIES[i] for i in labels]
    boxes = predictions['boxes']

    template = "{}: {:.2f}"
    for box, score, label in zip(boxes, scores, labels):
        x, y = box[:2]
        s = template.format(label, score)
        cv2.putText(
            image, s, (int(x)+5, int(y)+20), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1
        )

    return image


def predict(img, model):
    cv_img = np.array(img)[:, :, [2, 1, 0]]
    img_tensor = torchvision.transforms.functional.to_tensor(img)
    with torch.no_grad():
        output = model([img_tensor.cuda()])
    top_predictions = select_top_predictions(output[0], 0.7)
    top_predictions = {k: v.cpu() for k, v in top_predictions.items()}
    result = cv_img.copy()
    result = overlay_boxes(result, top_predictions)
    if 'masks' in top_predictions:
        result = overlay_mask(result, top_predictions)
    if 'keypoints' in top_predictions:
        result = overlay_keypoints(result, top_predictions)
    result = overlay_class_names(result, top_predictions)
    return result, output, top_predictions


def show(img, results, threshold=0.5):
    """
    Creates a image which contains all the bboxes and masks of the results as overlay.

    :param img: PIL image which is used to overlay the detected objects.
    :param results: The output from the detection process.
    :param threshold: The threshold to use when selecting from the results.
    :return: The image where the results have been overlayed.
    """
    cv_img = np.array(img)[:, :, [2, 1, 0]]
    top_predictions = select_top_predictions(results[0], threshold)
    top_predictions = {k: v.cpu() for k, v in top_predictions.items()}
    result = cv_img.copy()
    result = overlay_boxes(result, top_predictions)
    if 'masks' in top_predictions:
        result = overlay_mask(result, top_predictions)
    if 'keypoints' in top_predictions:
        result = overlay_keypoints(result, top_predictions)
    result = overlay_class_names(result, top_predictions)
    return result, results, top_predictions


def get_image(img_fn):
    """
    Loads and returns the image given by img_fn.
    Performs an transformation to align the image according to the orientation given in EXIF data.

    :param img_fn: Path and file name of the image.
    :return: The PIL image
    """
    from PIL import Image, ImageOps
    image = Image.open(img_fn).convert("RGB")
    image = ImageOps.exif_transpose(image)
    w, h = image.size
    if max(w, h) > 640:
        image = torchvision.transforms.functional.resize(image, 640)
    return image


def save_result(result, img_fn):
    cv2.imwrite(img_fn, result)

def free_memory():
    import gc
    gc.collect()
    torch.cuda.empty_cache()

def get_device():
    if torch.cuda.is_available():
        print(f'GPU: {torch.cuda.get_device_name(0)}')
        torch.cuda.empty_cache()
        device = torch.device('cuda')
    else:
        device = torch.device('cpu')
    print(f'Device: {device}')

    return device


def get_model(device: 'cpu'):
    print(mask_rcnn.model_urls)
    model = mask_rcnn.maskrcnn_resnet50_fpn(pretrained=True)
    if torch.cuda.is_available():
        model.to(device)
    print(model.eval())
    return model


def detect_in_image(img, model):
    img_tensor = torchvision.transforms.functional.to_tensor(img)
    if torch.cuda.is_available():
        img_tensor = img_tensor.cuda()
    with torch.no_grad():
        predictions = model([img_tensor])
    return predictions