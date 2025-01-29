""" Reads jpg with data that Robi scales produce and extracts the data from it.
"""
import json
from datetime import datetime
import sqlite3
import pytesseract
# from PIL import Image
import cv2
# import numpy as np
from os import listdir
from os.path import isfile, join

SQLITE_DB = "/Volumes/backup/sqlite/fitdays_health_data.db"
DOWNLOAD_FOLDER = "/Users/marcel-jankrijgsman/Downloads"
# DOWNLOAD_FOLDER = "/Volumes/backup/Health/Robo S11 shared data"
# ROBI_IMAGE = "/Users/marcel-jankrijgsman/Downloads/IMG_DF9D52131FAD-1.jpeg"


def read_extract_json(measurement_json_file):
    # open the json file with measurement names
    with open(measurement_json_file, "r", encoding="utf8") as json_file:
        # read the file
        measurement_names = json_file.read()
        # print the data
        return json.loads(measurement_names)


def get_text_from_image(image):
    # Get text from image
    imagetext = pytesseract.image_to_string(image)
    return imagetext


def get_date_from_image(image):
    """ get_date_from_image

        This function reads an image from the Fitdays app
        and first crops it to the top 290 pixels.
        This is where the username and date and time are located.

    Args:
        image (str): Name of the image file

    Returns:
        str: Username from the image
        str: Date and time from the image
    """
    # First read image with cv2
    cv2im = cv2.imread(image, cv2.IMREAD_COLOR)
    # Crop the image to only the top 290 pixels
    cv2im_top = cv2im[0:290, 0:cv2im.shape[1]]

    # Write the cropped image to a file
    # cv2.imwrite(f"cv2image_top.jpeg", cv2im_top)

    # Print text from the image
    image_text = pytesseract.image_to_string(cv2im_top)
    print(f"Image text: {image_text}")

    # Get text from the second line
    lines = image_text.split("\n")
    username = lines[0]
    date_text = lines[1]
    print(f"Date text: {date_text}")
    datetime_text = datetime.strptime(date_text,'%H:%M %d/%m/%Y')
    print(f"Date time text: {datetime_text.strftime('%Y-%m-%d %H:%M:00.000')}")

    return username, datetime_text.strftime('%Y-%m-%d %H:%M:00.000')


def rework_image(image_name, colourconversion = cv2.COLOR_BGR2GRAY, apply_rescale=True, resize_x=2, resize_y=2,
                 apply_threshold=True, threshold_type=cv2.THRESH_BINARY + cv2.THRESH_OTSU):
    """ Rework the image so it can be used for OCR

    Args:
        image_name (cv2 image): image to be reworked
        colourconversion (_type_, optional): _description_. Defaults to cv2.COLOR_BGR2GRAY.
        rescale (bool, optional): _description_. Defaults to True.
        resize_x (int, optional): _description_. Defaults to 2.
        resize_y (int, optional): _description_. Defaults to 2.

    Returns:
        _type_: _description_
    """    
    # im = Image.open("IMG_44254DD16026-1.jpeg") # the ROBI image with data
    cvim = cv2.imread(image_name, cv2.IMREAD_COLOR)

    # Convert colour space of the image (default is to grey)
    if colourconversion is not None:
        cvim = cv2.cvtColor(cvim, colourconversion)
        # cv2.imwrite(f"{image_name}_converted.jpeg", cvim)
    # Rescale the image, if needed.
    # imrescaled = cv2.resize(cvim, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    if apply_rescale:
        cvim = cv2.resize(cvim, None, fx=resize_x, fy=resize_y, interpolation=cv2.INTER_CUBIC)
        # cv2.imwrite(f"{image_name}_rescaled.jpeg", cvim)

    # Apply threshold to get image with only b&w (binarization)
    # Image Thresholding is an intensity transformation function in which the values of pixels below
    # a particular threshold are reduced, and the values above that threshold are boosted.  This
    # generally results in a bilevel image at the end, where the image is composed of black and white
    # pixels.
    if apply_threshold:
        cvim = cv2.threshold(cvim, 127, 255, threshold_type)[1]
        # cv2.imwrite(f"{image_name}_threshold.jpeg", cvim)

    return cvim


def interpret_text(ocr_text, unprocessed_image, robi_date, robi_user, measurement_names_json):
    # Create an empty dictionary to store the data
    health_dict = {}
    health_dict["Date"] = robi_date
    health_dict["Username"] = robi_user
    health_dict["Image_name"] = unprocessed_image

    # First split the text in lines
    lines = ocr_text.split("\n")
    for line in lines:
        # print(f"line: {line}")

        # Go through the measurement names in the json file
        for measurement_item in measurement_names_json['measurements']:

            # Search for the measurement name in the line
            if measurement_item['string_in_line'] in line:
                print(f"{line}")
                # The name of the measurement is the key
                key  = measurement_item['name']

                # The value in the line is the value
                value = line.split(" ")[1]

                # Check if value starts with a number
                # Because there are some lines where
                # the name can be found, but it isn't followed
                # by a number
                if value[0].isdigit():
                    # Remove the unit at the end of the value
                    print(f"Value: {value}")

                    # If there is a unit at the end of the value, remove it
                    # But also check that there is a unit after the value
                    if measurement_item['unit'] in value and measurement_item['unit'] != "":
                        print(f"Unit: {measurement_item['unit']}")
                        value_just_digit = value.split(measurement_item['unit'])[0]
                        print(f"Value just digit: {value_just_digit}")
                        health_dict[key] = value_just_digit # .replace(".", ",")
                    else:
                        health_dict[key] = value # .replace(".", ",")

    return health_dict


# 4150:4220, 150:400
def get_segment_data(image_name, start_x, end_x, start_y, end_y):
    # Read the image
    cv2im = cv2.imread(image_name, cv2.IMREAD_COLOR)
    # Crop the image to the arm left
    cv2im_segment = cv2im[start_y:end_y, start_x:end_x]

    # Write the cropped image to disk
    # cv2im_armleft_file = "cv2im_armleft_cropped.jpg"
    # cv2.imwrite(cv2im_armleft_file, cv2im_armleft)
    
    # Get text from the image. psm 6 is for a single uniform block of text.
    segment_text = pytesseract.image_to_string(cv2im_segment, config='--psm 6')
    # Print text from the image

    # Remove _, — and - signs from the text
    # These pop up when the underlining is misinterpreted
    segment_text = segment_text.replace("_", "").replace("-", "").replace("—", "")
    return segment_text


def get_list_of_processed_images(sqlite_db):
    # Get list of processed images from the database
    conn = sqlite3.connect(sqlite_db)
    c = conn.cursor()
    query = """SELECT Image_name
                FROM measurements
                """
    c.execute(query)
    rows = c.fetchall()
    conn.close()

    # Get image names without path. But there are None types.
    rows = [row[0].split("/")[-1] for row in rows if row[0] is not None]
    return rows


# Look for new IMG_nnnnnn.jpeg images in Downloads folder
# and process them
def get_images_in_folder(download_folder):
    # Get list of IMG.jpeg files in the download folder
    onlyfiles = [f for f in listdir(download_folder) if isfile(join(download_folder, f)) and f.startswith("IMG_") and f.endswith(".jpeg")]

    # Also append a list of files named JPEG-afbeelding-44F2-B7FA-C4-0.jpeg
    onlyfiles.extend([f for f in listdir(download_folder) if isfile(join(download_folder, f)) and f.startswith("JPEG-afbeelding") and f.endswith(".jpeg")])

    # # Get list of IMG.jpeg files with path
    # onlyfiles = [join(download_folder, f) for f in onlyfiles]

    # print(f"onlyfiles: {onlyfiles}")
    return onlyfiles


def find_unprocessed_images(image_files, processed_images):
    # Find the unprocessed images
    unprocessed_images = []
    for image_file in image_files:
        if image_file not in processed_images:
            unprocessed_images.append(image_file)
    
    # print(f"Unprocessed images: {unprocessed_images}")
    return unprocessed_images


def check_resolution_of_image(image_name):
    # Check that the resolution is 1290x7509
    im = cv2.imread(image_name, cv2.IMREAD_COLOR)
    # print(f"Image: {image_name}")
    # Check that image has shape
    if im is None:
        return False
    
    # print(f"Resolution: {im.shape}")
    if im.shape[0] == 7509 and im.shape[1] == 1290:
        return True
    else:
        return False
    

if __name__ == "__main__":
    # Get measurement names from json file
    measurement_names_json = read_extract_json("measurement_names.json")

    images_in_downloads = get_images_in_folder(DOWNLOAD_FOLDER)
    # print(f"Images in downloads: {images_in_downloads}")
    processed_images = get_list_of_processed_images(SQLITE_DB)
    # print(f"Processed images: {processed_images}")
    unprocessed_images = find_unprocessed_images(images_in_downloads, processed_images)

    # Add the path to the image
    unprocessed_images = [join(DOWNLOAD_FOLDER, image) for image in unprocessed_images]

    # Check the resolution of unprocessed images
    unprocessed_images = [image for image in unprocessed_images if check_resolution_of_image(image) == True]
    print(f"Unprocessed images with correct resolution: {unprocessed_images}")        
    

    for unprocessed_image in unprocessed_images:

        # Get the date from the image.
        robi_user, robi_date = get_date_from_image(unprocessed_image)

        # Save the image to a file
        # cv2.imwrite(f"{ROBI_IMAGE}_rescaled.jpeg", imbin)
        print("Trying to extract data from image no grayscale and no rescaling")
        # Get text from image, language is Dutch
        text = get_text_from_image(unprocessed_image)

        # Interpret the text
        health_dict = interpret_text(text, unprocessed_image, robi_date, robi_user, measurement_names_json)
        print(health_dict)

        # Check if gewicht has value in the dictionary
        if "Gewicht" in health_dict or "BMR" in health_dict:
            print(f"Gewicht: {health_dict['Gewicht']}")
            print(f"BMR: {health_dict['BMR']}")
        else:
            # OCR didn't find the weight
            print("Gewicht or BMR not found in first attempt")
            # Retry with different rescaling
            print("Trying to extract data from image with grayscale conversion and rescaling 1,5 times")
            imbin2 = rework_image(unprocessed_image, cv2.COLOR_BGR2GRAY, True, 1.5, 1.5, True, 
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Save the image to a file
            # cv2.imwrite(f"{ROBI_IMAGE}_rescaled2.jpeg", imbin2)

            # Get text from image, language is Dutch
            text2 = get_text_from_image(imbin2)
            health_dict2 = interpret_text(text2, unprocessed_image, robi_date, robi_user, measurement_names_json)

            if "Gewicht" in health_dict2 or "BMR" in health_dict2:
                print(f"Gewicht (attempt 2): {health_dict2['Gewicht']}")
                print(f"BMR (attempt 2): {health_dict2['BMR']}")
                health_dict = health_dict2
            else:
                print("Gewicht or BMR not found in second attempt")
                print("Trying to extract data from image with grayscale conversion and rescaling 2 times")
                imbin3 = rework_image(unprocessed_image, cv2.COLOR_BGR2GRAY, True, 2, 2, True, 
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                # cv2.imwrite(f"{unprocessed_image}_rescaled3.jpeg", imbin3)
                # Get text from image, language is Dutch
                text3 = get_text_from_image(imbin3)
                health_dict3 = interpret_text(text3, unprocessed_image, robi_date, robi_user, measurement_names_json)

                if "Gewicht" in health_dict3 or "BMR" in health_dict3:
                    print(f"Gewicht (attempt 3): {health_dict3['Gewicht']}")
                    print(f"BMR (attempt 3): {health_dict3['BMR']}")
                    health_dict = health_dict3
                else:
                    print("Gewicht not found in third attempt")

                # print("Trying to extract data from image without colour conversion and rescaling 2 times")
                # imbin3 = rework_image(unprocessed_image, None, True, 2, 2, True, 
                #             cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Arm left fat box: 4150:4220, 150:400
        armleftfat = get_segment_data(unprocessed_image, 150, 400, 4150, 4220)
        # Remove kg from the value
        armleftfat = armleftfat.split("kg")[0]
        # print(f"Arm left fat: {armleftfat}")
        health_dict["fatarmleft"] = armleftfat
        # Arm right fat box: 4150:4220, 850:1200
        armrightfat = get_segment_data(unprocessed_image, 850, 1200, 4150, 4220)
        armrightfat = armleftfat.split("kg")[0]
        # print(f"Arm right fat: {armrightfat}")
        health_dict["fatarmright"] = armrightfat
        # Stomach fat box: 4150:4220, 850:1200
        stomachfat = get_segment_data(unprocessed_image, 150, 400, 4425, 4500)
        stomachfat = stomachfat.split("kg")[0]
        # print(f"Stomach fat: {stomachfat}")
        health_dict["fatstomach"] = stomachfat
        legleftfat = get_segment_data(unprocessed_image, 150, 400, 4715, 4780)
        # Remove kg from the value
        legleftfat = legleftfat.split("kg")[0]
        # print(f"Arm left fat: {armleftfat}")
        health_dict["fatlegleft"] = legleftfat
        legrightfat = get_segment_data(unprocessed_image, 850, 1200, 4715, 4780)
        legrightfat = legrightfat.split("kg")[0]
        # print(f"Leg right fat: {armrightfat}")
        health_dict["fatlegright"] = legrightfat
        print(f"Fat arm left: {armleftfat}, arm right: {armrightfat}, stomach: {stomachfat}, leg left: {legleftfat}, leg right: {legrightfat}")

        # Arm left muscle
        armleftmuscle = get_segment_data(unprocessed_image, 150, 400, 5475, 5540)
        # Remove kg from the value
        armleftmuscle = armleftmuscle.split("kg")[0]
        health_dict["musclearmleft"] = armleftmuscle
        # Arm right muscle
        armrightmuscle = get_segment_data(unprocessed_image, 850, 1200, 5475, 5540)
        armrightmuscle = armrightmuscle.split("kg")[0]
        health_dict["musclearmright"] = armrightmuscle
        # Stomach muscle
        stomachmuscle = get_segment_data(unprocessed_image, 150, 400, 5750, 5810)
        stomachmuscle = stomachmuscle.split("kg")[0]
        health_dict["musclestomach"] = stomachmuscle
        # Leg left muscle
        legleftmuscle = get_segment_data(unprocessed_image, 150, 400, 6030, 6100)
        # Remove kg from the value
        legleftmuscle = legleftmuscle.split("kg")[0]
        health_dict["musclelegleft"] = legleftmuscle
        # Leg right muscle
        legrightmuscle = get_segment_data(unprocessed_image, 850, 1200, 6030, 6100)
        legrightmuscle = legrightmuscle.split("kg")[0]
        health_dict["musclelegright"] = legrightmuscle
        print(f"Muscle: arm left: {armleftmuscle}, arm right: {armrightmuscle}, stomach: {stomachfat}, leg left: {legleftfat}, leg right: {legrightfat}")


        # Write the health dictionary to a csv file
        # With keys as columns and values as rows
        with open("health_data.csv", "w", encoding="utf8") as file:
            # Write the header with the keys
            file.write(";".join(health_dict.keys()) + "\n")
            # Write the values
            file.write(";".join(health_dict.values()) + "\n")

        # Write the health dictionary to a database
        # With keys as columns and values as rows
        conn = sqlite3.connect(SQLITE_DB)
        c = conn.cursor()

        # Create table statement:
        create_table = """CREATE TABLE IF NOT EXISTS measurements 
            (Device_name TEXT,
            Username TEXT,
            Measurement_datetime DATETIME, 
            Image_name TEXT,
            Gewicht REAL, 
            BMI REAL, 
            Lichaamsvet REAL, 
            Vetmassa REAL, 
            Spiermassa REAL, 
            Spiersnelheid REAL, 
            Skeletspier REAL, 
            Botmassa REAL, 
            Eiwitmassa REAL, 
            Eiwit REAL, 
            Watergewicht REAL, 
            Lichaamswater REAL, 
            BMR INT, 
            WHR REAL)
        """

        # Print the create table statement
        # print(create_table)
        # Create a table with the keys as columns
        c.execute(create_table)

        # Insert statement
        insert_statement = """INSERT INTO measurements
        (Device_name, Username, Measurement_datetime, Image_name, Gewicht, Lichaamsvet, BMI, Watergewicht,
        Vetmassa, Spiermassa, Spiersnelheid, Skeletspier, Botmassa, Eiwitmassa, Eiwit, Lichaamswater, BMR, WHR,
        fatarmleft, fatarmright, fatstomach, fatlegleft, fatlegright, musclearmleft, musclearmright, musclestomach,
        musclelegleft, musclelegright)
        VALUES 
        ('Robi S11' , :Username, DATETIME(:Date), :Image_name, 
        :Gewicht, :Lichaamsvet, :BMI, :Watergewicht, :Vetmassa, :Spiermassa, :Spiersnelheid, :Skeletspier, 
        :Botmassa, :Eiwitmassa, :Eiwit, :Lichaamswater, :BMR, :WHR, :fatarmleft, :fatarmright, :fatstomach,
        :fatlegleft, :fatlegright, :musclearmleft, :musclearmright, :musclestomach, :musclelegleft, :musclelegright)
        """


        # Print the insert statement:
        # print(insert_statement)
        # Insert the values
        c.execute(insert_statement, health_dict)
        conn.commit()
        conn.close()
