""" Reads jpg with data that Robi scales produce and extracts the data from it.
"""
import json
import logging
from datetime import datetime
from os import listdir
from os.path import isfile, join
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import cv2
import pandas as pd
import pytesseract
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SQLITE_DB = "fitdays_health_data.db"
SQLITE_COPY_TARGET = "/Volumes/backup/sqlite/fitdays_health_data.db"
DOWNLOAD_FOLDER = "/Users/marcel-jankrijgsman/Downloads"
BACKUP_FOLDER = "/Volumes/backup/Health/RoboS11Images"


class MeasurementExtractor:
    """Extract measurements from Robi scale images."""
    
    def __init__(self, measurement_json_path: str, db_path: str, download_folder: str):
        """Initialize the extractor with paths.
        
        Args:
            measurement_json_path: Path to the JSON file with measurement definitions
            db_path: Path to the SQLite database
            download_folder: Path to the folder with images to process
        """
        self.measurement_json_path = measurement_json_path
        self.db_path = db_path
        self.download_folder = download_folder
        self.measurement_names = self._load_measurement_names()
    
    def _load_measurement_names(self) -> Dict:
        """Load measurement names from JSON file."""
        try:
            with open(self.measurement_json_path, "r", encoding="utf8") as json_file:
                return json.loads(json_file.read())
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load measurement names: {e}")
            raise
    
    def get_unprocessed_images(self) -> List[str]:
        """Get list of unprocessed images with the correct resolution."""
        images = self._get_images_in_folder()
        processed_images = self._get_processed_images()
        unprocessed_images = self._find_unprocessed_images(images, processed_images)
        
        # Add full path to images
        unprocessed_paths = [join(self.download_folder, img) for img in unprocessed_images]
        
        # Filter by resolution
        return [img for img in unprocessed_paths if self._check_resolution(img)]
    
    def _get_images_in_folder(self) -> List[str]:
        """Get list of potential Robi scale images in the download folder."""
        files = listdir(self.download_folder)
        img_files = [
            f for f in files 
            if isfile(join(self.download_folder, f)) and 
            ((f.startswith("IMG_") and f.endswith(".jpeg")) or 
             (f.startswith("JPEG-afbeelding") and f.endswith(".jpeg")))
        ]
        return img_files
    
    def _get_processed_images(self) -> List[str]:
        """Get list of already processed images from the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT Image_name FROM measurements")
            rows = cursor.fetchall()
            conn.close()
            
            # Extract filenames without path from non-None entries
            return [Path(row[0]).name for row in rows if row[0] is not None]
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return []
    
    def _find_unprocessed_images(self, all_images: List[str], processed_images: List[str]) -> List[str]:
        """Find images that haven't been processed yet."""
        return [img for img in all_images if img not in processed_images]
    
    def _check_resolution(self, image_path: str) -> bool:
        """Check if image has the expected Robi scale resolution (1290x7509)."""
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            logger.warning(f"Could not read image: {image_path}")
            return False
        
        return img.shape[0] == 7509 and img.shape[1] == 1290
    
    def process_images(self) -> None:
        """Process all unprocessed images in the download folder."""
        unprocessed_images = self.get_unprocessed_images() 
        if not unprocessed_images:
            logger.info("No new images to process")
            return
        
        logger.info(f"Found {len(unprocessed_images)} new images to process")
        for image_path in unprocessed_images:
            try:
                self.process_single_image(image_path)
            except Exception as e:
                logger.error(f"Error processing image {image_path}: {e}")
    
    def process_single_image(self, image_path: str) -> None:
        """Process a single image and save the extracted data."""
        logger.info(f"Processing image: {image_path}")
        
        # Extract user and date
        username, date_time = self.get_date_from_image(image_path)
        logger.info(f"Image from {username} taken at {date_time}")
        
        # Initialize health data dictionary with metadata
        health_dict = {
            "Date": date_time,
            "Username": username,
            "Image_name": image_path
        }
        
        # Try to extract general measurements with different processing methods
        health_dict = self.extract_general_measurements(image_path, health_dict)
        
        # Extract body segment data
        health_dict = self.extract_segment_data(image_path, health_dict)

        # Extract 'Vetvrij lichaamsgewicht'
        health_dict = self.extract_vetvrij_lichaamsgewicht(image_path, health_dict)
        
        # Save data to outputs
        self.save_data(health_dict)
        logger.info(f"Successfully processed image: {image_path}")

        # Move processed image to BACKUP_FOLDER directory if specified
        if BACKUP_FOLDER:
            target_dir = Path(BACKUP_FOLDER)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / Path(image_path).name
            # Path(image_path).rename(target_path)
            # move using shutil.move to avoid cross-device link error
            import shutil
            shutil.move(image_path, target_path)
            logger.info(f"Moved processed image to {target_path}")
    

    def get_date_from_image(self, image_path: str) -> Tuple[str, str]:
        """Extract username and date from the top portion of the image.
        
        Args:
            image_path: Path to the image
            
        Returns:
            Tuple of (username, formatted_date_time)
        """
        # Read and crop image to top section
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        img_top = img[0:290, 0:img.shape[1]]
        
        # Extract text from the image
        image_text = pytesseract.image_to_string(img_top)
        logger.debug(f"Top text: {image_text}")
        
        # Parse username and date
        lines = image_text.split("\n")
        username = lines[0]
        date_text = lines[1]
        
        # Convert date string to datetime
        datetime_obj = datetime.strptime(date_text, '%H:%M %d/%m/%Y')
        formatted_date = datetime_obj.strftime('%Y-%m-%d %H:%M:00.000')
        
        return username, formatted_date
    
    def extract_general_measurements(self, image_path: str, health_dict: Dict) -> Dict:
        """Extract general measurements from the image using multiple approaches if needed.
        
        Args:
            image_path: Path to the image
            health_dict: Initial health data dictionary with metadata
            
        Returns:
            Updated health data dictionary with measurements
        """
        # First attempt: Original image without processing
        logger.info("Extracting data - attempt 1: no processing")
        text = pytesseract.image_to_string(image_path, config="--psm 6")
        result = self._interpret_text(text, health_dict)
        
        # Check if key measurements were found
        if self._has_key_measurements(result):
            return result
        
        # Second attempt: Grayscale and 1.5x scaling
        logger.info("Extracting data - attempt 2: grayscale + 1.5x scaling")
        processed_img = self._preprocess_image(
            image_path, 
            color_conversion=cv2.COLOR_BGR2GRAY,
            xscale=1.5,
            yscale=1.5,
            apply_threshold=True
        )
        text = pytesseract.image_to_string(processed_img)
        result = self._interpret_text(text, health_dict)
        
        if self._has_key_measurements(result):
            return result
        
        # Third attempt: Grayscale and 2x scaling
        logger.info("Extracting data - attempt 3: grayscale + 2x scaling")
        processed_img = self._preprocess_image(
            image_path, 
            color_conversion=cv2.COLOR_BGR2GRAY,
            xscale=2.0,
            yscale=2.0,
            apply_threshold=True
        )
        text = pytesseract.image_to_string(processed_img)
        result = self._interpret_text(text, health_dict)

        if self._has_key_measurements(result):
            return result

        # Fourth attempt: COLOR_BGR2GRAY and x 1.7x, y 1.7x scaling
        logger.info("Extracting data - attempt 4: gray + x 1.7x, y 1.7x scaling")
        processed_img = self._preprocess_image(
            image_path, 
            color_conversion=cv2.COLOR_BGR2GRAY,
            xscale=1.7,
            yscale=1.7,
            apply_threshold=True
        )
        # (psm 6 = single uniform block of text)
        text = pytesseract.image_to_string(processed_img, config="--psm 6")
        result = self._interpret_text(text, health_dict)

        # Return the best result we have
        return result
    
    def _has_key_measurements(self, health_dict: Dict) -> bool:
        """Check if dictionary contains key measurements (Gewicht or BMR)."""
        return "Gewicht" in health_dict or "BMR" in health_dict
    
    def _preprocess_image(
        self, 
        image_path: str, 
        color_conversion: Optional[int] = None, 
        xscale: float = 1.0,
        yscale: float = 1.0,
        apply_threshold: bool = False,
        threshold_type: int = cv2.THRESH_BINARY + cv2.THRESH_OTSU
    ) -> Any:
        """Preprocess image for better OCR results.
        
        Args:
            image_path: Path to the image
            color_conversion: OpenCV color conversion constant
            scale: Scale factor for image resizing
            apply_threshold: Whether to apply thresholding
            threshold_type: OpenCV threshold type
            
        Returns:
            Processed image
        """
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        
        # Convert color space if specified
        if color_conversion is not None:
            img = cv2.cvtColor(img, color_conversion)
        
        # Resize if needed
        if xscale != 1.0 or yscale != 1.0:
            img = cv2.resize(img, None, fx=xscale, fy=yscale, interpolation=cv2.INTER_CUBIC)
        
        # Apply threshold if needed
        if apply_threshold:
            img = cv2.threshold(img, 127, 255, threshold_type)[1]
        
        return img
    
    def _interpret_text(self, ocr_text: str, base_dict: Dict) -> Dict:
        """Interpret OCR text and extract measurements.
        
        Args:
            ocr_text: Text extracted from OCR
            base_dict: Dictionary with metadata
            
        Returns:
            Dictionary with extracted measurements
        """
        # Create a new dictionary with the base data
        health_dict = base_dict.copy()
        previous_line = None
        
        # Process each line of OCR text
        for line in ocr_text.split("\n"):
            # Check each measurement from the JSON definition
            # print(f"Previous line: {previous_line}, Current line: {line}")
            # if line in "Vetvrij":
            #     previous_line = line
            # elif line == "Ideaal":
            #     previous_line = None

            for measure in self.measurement_names['measurements']:
                if measure['string_in_line'] in line:
                    logger.debug(f"Found measurement: {line}")
                    key = measure['name'].replace(" ", "")
                    # Remove key from line to isolate value
                    line = line.replace(measure['string_in_line'], "").strip()

                    parts = line.split(" ")
                    
                    # Skip lines that don't have a value
                    # if len(parts) < 2:
                    #     print(f"Skipping line because {len(parts)} parts found: {line}")
                    #     continue
                    
                    value = parts[0]

                    # Check if value starts with a digit
                    if not value or not value[0].isdigit():
                        continue
                    
                    
                    # Remove 4g as misspelling of kg for vetvrije massa
                    if key == "Vetvrijlichaamsgewicht" and "4g" in value:
                        value = value.replace("4g", "kg")

                    # Remove unit if present
                    if measure['unit'] and measure['unit'] in value:
                        value = value.split(measure['unit'])[0]

                    # # Special cases for keys with names on multiple lines
                    # if key == "lichaamsgewicht" and previous_line == "Vetvrij":
                    #     key = "Vetvrijlichaamsgewicht"
                    # elif key == "Vetvrij" and previous_line == "lichaamsgewicht":
                    #     key = "Ideaallichaamsgewicht"

                    health_dict[key] = value


        # print(health_dict)
        return health_dict
    
    def extract_segment_data(self, image_path: str, health_dict: Dict) -> Dict:
        """Extract body segment data (fat and muscle) from specific regions.
        
        Args:
            image_path: Path to the image
            health_dict: Dictionary with metadata and general measurements
            
        Returns:
            Updated dictionary with segment data
        """
        # Definition of segment regions (x_start, x_end, y_start, y_end, name)
        segments = [
            # Fat segments
            (150, 400, 4150, 4220, "fatarmleft"),
            (850, 1200, 4150, 4220, "fatarmright"),
            (150, 400, 4425, 4500, "fatstomach"),
            (150, 400, 4715, 4780, "fatlegleft"),
            (850, 1200, 4715, 4780, "fatlegright"),
            
            # Muscle segments
            (150, 400, 5475, 5540, "musclearmleft"),
            (850, 1200, 5475, 5540, "musclearmright"),
            (150, 400, 5750, 5810, "musclestomach"),
            (150, 400, 6030, 6100, "musclelegleft"),
            (850, 1200, 6030, 6100, "musclelegright")
        ]
        
        # Extract data for each segment
        for x_start, x_end, y_start, y_end, name in segments:
            text = self._get_segment_text(image_path, x_start, x_end, y_start, y_end)
            # Remove 'kg' and store the value
            value = text.split("kg")[0] if "kg" in text else text
            health_dict[name] = value
        
        return health_dict
    
    def extract_vetvrij_lichaamsgewicht(self, image_path: str, health_dict: Dict) -> Dict:
        """Extract 'Vetvrij lichaamsgewicht' from a specific segment of the image.
        It is hard to get this data from the general OCR text, because the
        name is split over two lines.
        
        Args:
            image_path: Path to the image
            health_dict: Dictionary with metadata and general measurements
        Returns:
            Updated dictionary with 'Vetvrij lichaamsgewicht' value
        """
        print("Start extract_vetvrij_lichaamsgewicht")
        # Define segment coordinates
        x_start, x_end = 600, 780
        y_start, y_end = 1300, 1380
        
        text = self._get_segment_text(image_path, x_start, x_end, y_start, y_end)
        print(f"Vetvrij lichaamsgewicht segment text: {text}")
        # Extract value before 'kg'
        if "kg" in text:
            value = text.split("kg")[0].strip()
            print(f"Extracted Vetvrij lichaamsgewicht value: {value}")
            health_dict["Vetvrijlichaamsgewicht"] = value
        
        return health_dict

    def _get_segment_text(self, image_path: str, x_start: int, x_end: int, y_start: int, y_end: int) -> str:
        """Extract text from a specific segment of the image.
        
        Args:
            image_path: Path to the image
            x_start, x_end, y_start, y_end: Coordinates of the segment
            
        Returns:
            Extracted text
        """
        # Read the image
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        
        # Crop to segment
        img_segment = img[y_start:y_end, x_start:x_end]
        
        # Get text (psm 6 = single uniform block of text)
        segment_text = pytesseract.image_to_string(img_segment, config='--psm 6')
        
        # Clean text (remove underline characters often misinterpreted)
        segment_text = segment_text.replace("_", "").replace("-", "").replace("—", "")
        
        return segment_text
    
    def save_data(self, health_dict: Dict) -> None:
        """Save extracted data to CSV, Excel and SQLite.
        
        Args:
            health_dict: Dictionary with extracted health data
        """
        self._save_to_csv(health_dict)
        self._save_to_excel(health_dict)
        self._save_to_database(health_dict)
    
    def _save_to_csv(self, health_dict: Dict) -> None:
        """Save data to CSV file."""
        try:
            with open("health_data.csv", "w", encoding="utf8") as file:
                # Write header (keys)
                file.write(";".join(health_dict.keys()) + "\n")
                # Write values
                file.write(";".join(health_dict.values()) + "\n")
            logger.info("Data saved to CSV")
        except IOError as e:
            logger.error(f"Error saving to CSV: {e}")
    
    def _save_to_excel(self, health_dict: Dict) -> None:
        """Save data to Excel file."""
        try:
            df = pd.DataFrame(health_dict, index=[0])
            df.to_excel("health_data.xlsx")
            logger.info("Data saved to Excel")
        except Exception as e:
            logger.error(f"Error saving to Excel: {e}")
    
    def _save_to_database(self, health_dict: Dict) -> None:
        """Save data to SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            self._create_database_table(cursor)
            
            # Insert data
            self._insert_data(cursor, health_dict)
            
            conn.commit()
            conn.close()
            logger.info("Data saved to database")

            # Copy database to backup location
            if SQLITE_COPY_TARGET:
                Path(SQLITE_COPY_TARGET).parent.mkdir(parents=True, exist_ok=True)
                with open(self.db_path, "rb") as src, open(SQLITE_COPY_TARGET, "wb") as dst:
                    dst.write(src.read())
                logger.info(f"Database copied to {SQLITE_COPY_TARGET}")
                
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
    
    def _create_database_table(self, cursor: sqlite3.Cursor) -> None:
        """Create the measurements table if it doesn't exist."""
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
            WHR REAL,
            fatarmleft TEXT,
            fatarmright TEXT,
            fatstomach TEXT,
            fatlegleft TEXT,
            fatlegright TEXT,
            musclearmleft TEXT,
            musclearmright TEXT,
            musclestomach TEXT,
            musclelegleft TEXT,
            musclelegright TEXT,
            onderhuidsvet REAL,
            visceraalvet REAL,
            Vetvrijemassa REAL,
            Lichaamsleeftijd INT)
        """
        cursor.execute(create_table)
    
    def _insert_data(self, cursor: sqlite3.Cursor, health_dict: Dict) -> None:
        """Insert health data into the database."""
        insert_statement = """INSERT INTO measurements
        (Device_name, Username, Measurement_datetime, Image_name, Gewicht, Lichaamsvet, BMI, Watergewicht,
        Vetmassa, Spiermassa, Spiersnelheid, Skeletspier, Botmassa, Eiwitmassa, Eiwit, Lichaamswater, BMR, WHR,
        fatarmleft, fatarmright, fatstomach, fatlegleft, fatlegright, musclearmleft, musclearmright, musclestomach,
        musclelegleft, musclelegright, onderhuidsvet, visceraalvet, Vetvrijemassa, Lichaamsleeftijd)
        VALUES 
        ('Robi S11' , :Username, DATETIME(:Date), :Image_name, 
        :Gewicht, :Lichaamsvet, :BMI, :Watergewicht, :Vetmassa, :Spiermassa, :Spiersnelheid, :Skeletspier, 
        :Botmassa, :Eiwitmassa, :Eiwit, :Lichaamswater, :BMR, :WHR, :fatarmleft, :fatarmright, :fatstomach,
        :fatlegleft, :fatlegright, :musclearmleft, :musclearmright, :musclestomach, :musclelegleft, :musclelegright,
        :Onderhuidsvet, :Visceraalvet, :Vetvrijlichaamsgewicht, :Lichaamsleeftijd)
        """
        cursor.execute(insert_statement, health_dict)


def main():
    """Main function to run the extractor."""
    try:
        extractor = MeasurementExtractor(
            measurement_json_path="measurement_names.json",
            db_path=SQLITE_DB,
            download_folder=DOWNLOAD_FOLDER
        )
        extractor.process_images()
    except Exception as e:
        logger.error(f"Error running extractor: {e}")


if __name__ == "__main__":
    main()