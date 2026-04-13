import glob
import os
import shutil
import subprocess

import click

BATCH_SIZE = 200


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

    # Run mogrify commands in batches for ARG_MAX safety
    png_files = glob.glob(os.path.join(resized_dir, "*.png"))
    for i in range(0, len(png_files), BATCH_SIZE):
        batch = png_files[i : i + BATCH_SIZE]
        subprocess.run(["mogrify", "-resize", "50x50", "--", *batch], check=True)
        subprocess.run(["mogrify", "-format", "png", "-alpha", "on", "--", *batch], check=True)
        subprocess.run(["mogrify", "-fill", "black", "-colorize", "100", "--", *batch], check=True)


if __name__ == "__main__":
    process_images()
