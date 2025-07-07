#!/usr/bin/env python3

import argparse
import logging
import pathlib
import struct  # For unpacking binary data
import os  # For checking file existence

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FileCarver:
    """
    Recovers potentially deleted files from a raw disk image or file,
    based on file type headers and footers.
    """

    def __init__(self, image_path, output_dir, file_types, block_size=512):
        """
        Initializes the FileCarver.

        Args:
            image_path (str): Path to the disk image or file.
            output_dir (str): Directory to save recovered files.
            file_types (dict): Dictionary of file types with their headers and footers.
            block_size (int): Block size to read from the image. Defaults to 512.
        """
        self.image_path = image_path
        self.output_dir = output_dir
        self.file_types = file_types
        self.block_size = block_size
        self.logger = logging.getLogger(__name__)  # Get logger instance
        self.validate_input()  # Input validation at initialization


    def validate_input(self):
        """Validates the input parameters."""

        if not isinstance(self.image_path, str):
            raise TypeError("Image path must be a string.")
        if not isinstance(self.output_dir, str):
            raise TypeError("Output directory must be a string.")
        if not isinstance(self.file_types, dict):
            raise TypeError("File types must be a dictionary.")
        if not isinstance(self.block_size, int):
            raise TypeError("Block size must be an integer.")
        if self.block_size <= 0:
            raise ValueError("Block size must be a positive integer.")

        # Check if the image file exists
        if not os.path.exists(self.image_path):
            raise FileNotFoundError(f"Image file not found: {self.image_path}")

        # Create the output directory if it doesn't exist
        pathlib.Path(self.output_dir).mkdir(parents=True, exist_ok=True)


    def carve_files(self):
        """
        Carves files from the disk image based on file type signatures.
        """
        try:
            with open(self.image_path, 'rb') as f:
                data = f.read()

                for file_type, signatures in self.file_types.items():
                    header = signatures.get('header')
                    footer = signatures.get('footer')

                    if not header:
                        self.logger.warning(f"No header defined for file type: {file_type}. Skipping.")
                        continue  # Skip if no header is defined.

                    header_bytes = bytes.fromhex(header)  # Convert header from hex to bytes

                    start_indices = self._find_all(data, header_bytes)

                    for start_index in start_indices:
                        end_index = None
                        if footer:
                            footer_bytes = bytes.fromhex(footer)
                            end_indices = self._find_all(data[start_index:], footer_bytes)
                            if end_indices:  # Use the *first* footer after the header
                                end_index = start_index + end_indices[0] + len(footer_bytes)
                        else:
                            # If no footer is specified, try to carve a block_size chunk after the header.
                            end_index = start_index + self.block_size

                        if end_index:
                            # Extract the carved data
                            carved_data = data[start_index:end_index]

                            # Sanitize the filename using pathlib
                            filename = f"recovered_{start_index}_{file_type}.dat" # Or .jpg .png etc.
                            file_path = pathlib.Path(self.output_dir) / filename

                            try:
                                with open(file_path, 'wb') as outfile:
                                    outfile.write(carved_data)
                                self.logger.info(f"Recovered {file_type} file: {file_path}")
                            except Exception as e:
                                self.logger.error(f"Error writing file: {file_path}. Error: {e}")
        except FileNotFoundError:
            self.logger.error(f"Image file not found: {self.image_path}")
            raise
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            raise

    def _find_all(self, data, sub):
        """Find all occurrences of a sub-byte sequence within a byte sequence."""
        indices = []
        start = 0
        while True:
            try:
                start = data.index(sub, start)
            except ValueError:
                return indices
            indices.append(start)
            start += len(sub)
        return indices


def setup_argparse():
    """
    Sets up the argument parser for the command-line interface.
    """
    parser = argparse.ArgumentParser(description='File carving tool.')
    parser.add_argument('image', help='Path to the disk image or file.')
    parser.add_argument('output', help='Directory to save recovered files.')
    parser.add_argument('--blocksize', type=int, default=512, help='Block size to read (default: 512).')
    parser.add_argument('--filetypes', type=str, default="filetypes.txt", help='Path to the file containing file type signatures. (default: filetypes.txt)')
    parser.add_argument('--log', type=str, default="carver.log", help='Path to the log file. (default: carver.log)')
    return parser


def load_file_types(filetypes_path):
    """Loads file type signatures from a file. Supports simple key: value format."""
    file_types = {}
    try:
        with open(filetypes_path, 'r') as f:
            current_file_type = None
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):  # Skip empty lines and comments
                    continue
                if line.startswith('['): # start of a new file type
                    current_file_type = line[1:-1]
                    file_types[current_file_type] = {}
                elif '=' in line: # key value pairs for the file type
                    if not current_file_type:
                         raise ValueError("Invalid file type definition. Must start with a file type name in brackets.")
                    key, value = line.split('=', 1)
                    file_types[current_file_type][key.strip()] = value.strip()
    except FileNotFoundError:
        logging.error(f"File types file not found: {filetypes_path}")
        raise
    except Exception as e:
         logging.error(f"Error loading file types from {filetypes_path}: {e}")
         raise
    return file_types



def main():
    """
    Main function to parse arguments and run the file carving process.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    # Configure logging to file
    logging.basicConfig(filename=args.log, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger().addHandler(logging.StreamHandler()) # Also log to console


    try:
        file_types = load_file_types(args.filetypes)
        carver = FileCarver(args.image, args.output, file_types, args.blocksize)
        carver.carve_files()
        logging.info("File carving completed successfully.")
    except Exception as e:
        logging.error(f"File carving failed: {e}")


if __name__ == "__main__":
    # Example Usage:
    # Create a dummy image file:
    #   echo -n "Header12345DataDataDataFooterHeader67890MoreDataFooter" > test.img
    # Create a filetypes.txt:
    #   [testfile]
    #   header=486561646572
    #   footer=466f6f746572
    # Run the script:
    #   python file_carver.py test.img output_dir --filetypes filetypes.txt
    main()