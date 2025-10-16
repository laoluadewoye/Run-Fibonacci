from pathlib import Path
from subprocess import run, CompletedProcess
from glob import glob


def build_push_image(dockerfile_path, image_tag, dir_context, push=False):
    # Build image
    output: CompletedProcess = run(['docker', 'build', '-f', dockerfile_path, '-t', image_tag, dir_context])
    assert output.returncode == 0, output.stderr

    # Push image
    if push:
        output: CompletedProcess = run(['docker', 'push', image_tag])
        assert output.returncode == 0, output.stderr


# Push images
push_image = False

# Create constants
BASE_FOLDER: Path = Path(__file__).resolve().parent
latest_image: str = open(f'{BASE_FOLDER}/latest_image.adoc').read()
platforms: list[str] = [dockerfile.split('\\')[-1].split('.')[0] for dockerfile in glob(f'{BASE_FOLDER}/*Dockerfile')]

# Create platform specific
for platform in platforms:
    build_push_image(f'{platform}.Dockerfile', f'{latest_image}-{platform}', BASE_FOLDER, push_image)

# # Create defaults
build_push_image('alpine.Dockerfile', f'{latest_image.split(':')[0]}:latest', BASE_FOLDER, push_image)
build_push_image('alpine.Dockerfile', latest_image, BASE_FOLDER, push_image)
