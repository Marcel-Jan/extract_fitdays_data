""" Reads jpg with data that Robi scales produce and extracts the data from it.
"""
import json
import pytesseract
from PIL import Image



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


if __name__ == "__main__":
    # Get measurement names from json file
    measurement_names_json = read_extract_json("measurement_names.json")

    im = Image.open("IMG_F8788C972D49-1.jpeg") # the ROBI image with data
    # Get text from image, language is Dutch
    text = get_text_from_image(im)

    # Create an empty dictionary to store the data
    health_dict = {}

    # First split the text in lines
    lines = text.split("\n")
    for line in lines:
        # print(f"line: {line}")

        # Go through the measurement names in the json file
        for measurement_item in measurement_names_json['measurements']:

            # Search for the measurement name in the line
            if measurement_item['string_in_line'] in line:
                # print(f"{line}")
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
                        health_dict[key] = value_just_digit.replace(".", ",")
                    else:
                        health_dict[key] = value.replace(".", ",")
 
    print(health_dict)

    # Write the health dictionary to a csv file
    # With keys as columns and values as rows
    with open("health_data.csv", "w", encoding="utf8") as file:
        # Write the header with the keys
        file.write(";".join(health_dict.keys()) + "\n")
        # Write the values
        file.write(";".join(health_dict.values()) + "\n")
