""" Reads jpg with data that Robi scales produce and extracts the data from it.
"""
import json
from datetime import datetime
import sqlite3
import pytesseract
# from PIL import Image
import cv2
# import numpy as np


SQLITE_DB = "/Volumes/backup/sqlite/fitdays_health_data.db"
ROBI_IMAGE = "/Users/marcel-jankrijgsman/Downloads/IMG_B4D900CAA293-1.jpeg"


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
  
    # Rescale the image, if needed.
    # imrescaled = cv2.resize(cvim, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    if apply_rescale:
        cvim = cv2.resize(cvim, None, fx=resize_x, fy=resize_y, interpolation=cv2.INTER_CUBIC)

    # Apply threshold to get image with only b&w (binarization)
    # Image Thresholding is an intensity transformation function in which the values of pixels below
    # a particular threshold are reduced, and the values above that threshold are boosted.  This
    # generally results in a bilevel image at the end, where the image is composed of black and white
    # pixels.
    if apply_threshold:
        cvim = cv2.threshold(cvim, 127, 255, threshold_type)[1]

    return cvim


def interpret_text(ocr_text, robi_date, robi_user, measurement_names_json):
    # Create an empty dictionary to store the data
    health_dict = {}
    health_dict["Date"] = robi_date
    health_dict["Username"] = robi_user
    health_dict["Image_name"] = ROBI_IMAGE

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



if __name__ == "__main__":
    # Get measurement names from json file
    measurement_names_json = read_extract_json("measurement_names.json")

    # Get the date from the image.
    robi_user, robi_date = get_date_from_image(ROBI_IMAGE)

    print("Trying to extract data from image with grayscale conversion and rescaling 1,5 times")
    imbin = rework_image(ROBI_IMAGE, cv2.COLOR_BGR2GRAY, True, 1.5, 1.5, True, 
                         cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Save the image to a file
    cv2.imwrite(f"{ROBI_IMAGE}_rescaled.jpeg", imbin)

    # Get text from image, language is Dutch
    text = get_text_from_image(imbin)

    # Interpret the text
    health_dict = interpret_text(text, robi_date, robi_user, measurement_names_json)
    print(health_dict)

    # Check if gewicht has value in the dictionary
    if "Gewicht" in health_dict:
        print(f"Gewicht: {health_dict['Gewicht']}")
    else:
        # OCR didn't find the weight
        print("Gewicht not found in first attempt")
        # Retry with different rescaling
        print("Trying to extract data from image with grayscale conversion and rescaling 2 times")
        imbin2 = rework_image(ROBI_IMAGE, cv2.COLOR_BGR2GRAY, True, 2, 2, True, 
                         cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Save the image to a file
        cv2.imwrite(f"{ROBI_IMAGE}_rescaled2.jpeg", imbin2)

        # Get text from image, language is Dutch
        text2 = get_text_from_image(imbin2)
        health_dict2 = interpret_text(text2, robi_date, robi_user, measurement_names_json)

        if "Gewicht" in health_dict2:
            print(f"Gewicht (attempt 2): {health_dict2['Gewicht']}")
            health_dict = health_dict2
        else:
            print("Gewicht not found in second attempt")
            print("Trying to extract data from image without colour conversion and rescaling 2 times")
            imbin3 = rework_image(ROBI_IMAGE, None, True, 2, 2, True, 
                         cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            cv2.imwrite(f"{ROBI_IMAGE}_rescaled3.jpeg", imbin3)
            # Get text from image, language is Dutch
            text3 = get_text_from_image(imbin3)
            health_dict3 = interpret_text(text3, robi_date, robi_user, measurement_names_json)

            if "Gewicht" in health_dict3:
                print(f"Gewicht (attempt 3): {health_dict3['Gewicht']}")
                health_dict = health_dict3
            else:
                print("Gewicht not found in third attempt")

    

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
     Vetmassa, Spiermassa, Spiersnelheid, Skeletspier, Botmassa, Eiwitmassa, Eiwit, Lichaamswater, BMR, WHR)
    VALUES 
    ('Robi S11' , :Username, DATETIME(:Date), :Image_name, 
     :Gewicht, :Lichaamsvet, :BMI, :Watergewicht, :Vetmassa, :Spiermassa, :Spiersnelheid, :Skeletspier, 
     :Botmassa, :Eiwitmassa, :Eiwit, :Lichaamswater, :BMR, :WHR)
    """


    # Print the insert statement:
    # print(insert_statement)
    # Insert the values
    c.execute(insert_statement, health_dict)
    conn.commit()
    conn.close()
