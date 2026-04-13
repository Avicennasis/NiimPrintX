import glob
import os
import shutil
import subprocess

import click


@click.command()
@click.argument("image_directory", type=click.Path(exists=True))
def process_images(image_directory):
    # Create subdirectories
    original_dir = os.path.join(image_directory, "original")
    resized_dir = os.path.join(image_directory, "50x50")

    os.makedirs(original_dir, exist_ok=True)
    os.makedirs(resized_dir, exist_ok=True)

    # Copy files to subdirectories
    for filename in glob.glob(os.path.join(image_directory, "*.png")):
        shutil.copy(filename, original_dir)
        shutil.copy(filename, resized_dir)

    # Run mogrify commands
    png_files = glob.glob(os.path.join(resized_dir, "*.png"))
    if png_files:
        subprocess.run(["mogrify", "-resize", "50x50", "--", *png_files], check=True)
        subprocess.run(["mogrify", "-format", "png", "-alpha", "on", "--", *png_files], check=True)
        subprocess.run(["mogrify", "-fill", "black", "-colorize", "100", "--", *png_files], check=True)


if __name__ == "__main__":
    process_images()
