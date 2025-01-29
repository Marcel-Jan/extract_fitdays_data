import pytesseract
from pytesseract import Output
import cv2

def get_boundary_boxes(image):
    d = pytesseract.image_to_data(image, output_type=Output.DICT)
    n_boxes = len(d['level'])
    for i in range(n_boxes):
        (x, y, w, h) = (d['left'][i], d['top'][i], d['width'][i], d['height'][i])
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
    return image


ROBI_IMAGE = "/Users/marcel-jankrijgsman/Downloads/JPEG-afbeelding-44F2-B7FA-C4-0.jpeg"
image = cv2.imread(ROBI_IMAGE)
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (9,9), 0)
thresh = cv2.adaptiveThreshold(blur,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,11,30)
thresh2 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

d = pytesseract.image_to_data(image, output_type=Output.DICT)
n_boxes = len(d['level'])
for i in range(n_boxes):
    (x, y, w, h) = (d['left'][i], d['top'][i], d['width'][i], d['height'][i])
    cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)

# cv2.imshow('img', img)
# cv2.waitKey(0)
image_with_boxes = get_boundary_boxes(image)
cv2.imwrite(f"{ROBI_IMAGE}_boundaries.jpeg", image)

grayimage_with_boxes = get_boundary_boxes(gray)
cv2.imwrite(f"{ROBI_IMAGE}_gray_boundaries.jpeg", gray)

blurimage_with_boxes = get_boundary_boxes(blur)
cv2.imwrite(f"{ROBI_IMAGE}_blur_boundaries.jpeg", blur)

threshimage_with_boxes = get_boundary_boxes(thresh)
cv2.imwrite(f"{ROBI_IMAGE}_thresh_boundaries.jpeg", thresh)

thresh2image_with_boxes = get_boundary_boxes(thresh2)
cv2.imwrite(f"{ROBI_IMAGE}_thresh2_boundaries.jpeg", thresh2)

cv2im_top = image[0:290, 0:image.shape[1]]
cv2.imwrite(f"{ROBI_IMAGE}_top.jpeg", cv2im_top)