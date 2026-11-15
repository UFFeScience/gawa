# GAWA Version 2.0

## GAWA workflow

This is a code intended to identify stellar clusters using wavelet transformation in a catalog of stars filtered by isochronal masks.

The complete GAWA documentation is hosted [here](https://linea-it.github.io/gawa/).

### Instalation

Clone the repository and create an environment with Conda:
```bash
git clone https://github.com/linea-it/gawa && cd gawa 
conda create -n gawa python=3.9
conda activate gawa
conda install -c conda-forge cfitsio=3.430
conda install -c cta-observatory sparse2d
conda install jupyterlab
conda install ipykernel
pip install scikit-image
pip install astropy
pip install healpy
pip install parsl
ipython kernel install --user --name=gawa
```

Copy gawa.cfg and env.sh
```bash
cp gawa.cfg.template gawa.cfg
cp gawa.sh.template gawa.sh # You need to edit it if you want to run with Parsl in cluster.
```

### Running with Parsl(Pilot Jobs - Remote jobs)
Edit gawa.sh, adding the path to Conda (CONDAPATH) and the path to this repository (GAWA_ROOT):
```bash
export CONDAPATH=<conda path>
export GAWA_ROOT=<gawa repository path>
export PYTHONPATH=$PYTHONPATH:$GAWA_ROOT
export GAWA_LOG_LEVEL=info

source $CONDAPATH/activate
conda activate gawa
python -m ipykernel install --user --name=gawa
```
Choose the 'executor' option in gawa.cfg and run:
```bash
source gawa.sh
python -W ignore gawa_main.py gawa.cfg
```

### Running with JupyterLab

```bash
jupyter-lab gawazpy.ipynb
```

### Warnings

To run again the code, please remove the following folders with the command (being in the root folder):

```bash
rm -r tiles footprint isochrone_masks
```

and files:

```bash
rm tiles_specs.fits cluster.fits cluster0.fits
```

If you run with max_threads > 1, the kernel may die while running the main cell. We think that this is related to the memory required by the jobs. Set max_threads = 1 and run again.
---

## Running with Docker Compose (Parsl)

```bash
docker-compose up --build -d 

docker exec -it gawa bash

conda run --no-capture-output -n gawa python -W ignore gawa_main.py gawa.cfg
# conda run --no-capture-output -n gawa debugpy --listen 0.0.0.0:5678 --wait-for-client gawa_main.py gawa.cfg  # Debugging

```
## UFFeScience: one task per tile

This fork preserves the GAWA scientific routines and adds a tile-level CLI for
external workflow engines. The original Parsl entry point remains available.
The tile CLI calls the same worker functions directly, without starting Parsl.

Container image: `ghcr.io/uffescience/gawa:tiles-v1` (linux/amd64).
The UFFeScience organization currently blocks public packages, so this image
requires GHCR authentication and package access. Authenticate with
`docker login ghcr.io` using a token with `read:packages`, or configure the
executor's image-pull credentials. An organization administrator must allow
public packages before this image can be made anonymously downloadable.
For reproducible experiments, select the commit-SHA tag or image digest published
by the **Tile workflow** GitHub Action.

Inside the container, with a writable volume mounted at `/data-akoflow`:

```bash
conda run --no-capture-output -n gawa python /data/gawa_tasks.py prepare --count 14
conda run --no-capture-output -n gawa python /data/gawa_tasks.py tile --id 0
# Run one tile command for each ID 0..13, then:
conda run --no-capture-output -n gawa python /data/gawa_tasks.py merge
```

`prepare` copies the bundled inputs to an isolated workspace, normalizes the
configuration, creates the tiling and computes the common masks. It checks that
the generated IDs match the expected 0..13 reference tiles. Each `tile` command
processes exactly one tile. `merge` requires completion metadata from every tile
before applying the original global consolidation and filtering.

- [14 independent tile tasks](akoflow/gawa-tiles-14.yaml)
- [Same 14 tiles, at most four running together](akoflow/gawa-tiles-4.yaml)

Both workflows contain 16 activities: preparation, 14 tile tasks and consolidation.
The four-way version uses four fixed dependency chains, so a slow tile can leave
capacity idle; an executor-level dynamic concurrency limit is preferable when
available. Tile CPU/memory limits are starting values, not measured requirements.

Generate another cap without changing the scientific code:

```bash
python akoflow/generate_tiles.py --tiles 14 --parallel 2 --output akoflow/gawa-tiles-2.yaml
```

The examples retain the supplied legacy Akoflow YAML dialect and storage policy;
they are not a conversion to another Akoflow API version. All tasks must see the
same workspace. `hostpath` alone does not share files between nodes: start on a
single node or configure shared storage/validated artifact transfers. Use a fresh
volume for each experiment; do not run variants concurrently on the same volume.
Results are under `/data-akoflow/gawa-tiles-run/results/`.

The CLI also accepts `--workspace` and, for preparation, `--config`. Workspaces
must be outside `/data`. If all tiles have no detections, consolidation currently
returns an explicit error instead of inventing an empty scientific catalog.

Build locally with `docker build -f Dockerfile.tiles -t gawa:tiles .`.
The image extends the original pinned scientific environment with this fork's
code. CI tests orchestration and builds/publishes the image; these checks do not
constitute a scientific benchmark or catalog-validation experiment.
