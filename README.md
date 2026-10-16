# cad-render

Headless B-rep CAD as an HTTP service: turn [build123d](https://build123d.readthedocs.io) scripts into
STL / STEP / 3MF / PNG, convert and repair meshes, and generate CAD from a text prompt — made for
agents and scripts, one Docker container, file in / file out.

Parts are modelled in Python with build123d on OpenCascade, so fillets, chamfers and threads are exact
and STEP goes in and out. The service is stateless: one request is one file, results come back with
`X-Cad-*` headers (volume, bounding box, warnings, seconds) or as JSON with the worker log, and the CLI
reports distinct exit codes (`3` = empty geometry, which makes a fit check a one-liner). Text-to-CAD via
[Zoo](https://zoo.dev) and the hand-off to a [Bambuddy](https://github.com/maziggy/bambuddy) library
and slicer pipeline are both optional. The CLI, the API, writing parts, configuration, security and
development are documented in `docs/`.

![cad-render demo](docs/demo.png)

## Requirements

- Docker with the Compose plugin (the image is published for `linux/amd64` and `linux/arm64`).
- For the `bin/cad-render` CLI on the client: `bash`, `curl`, `tar` and `ruby`.
- Optional: a Zoo API token for `/zoo`; a Bambuddy URL and API key for `--to-bb`.

## Setup

```sh
git clone https://github.com/rojosinalma/cad-render.git
cd cad-render
cp .env.example .env            # add ZOO_API_TOKEN only if you want /zoo
docker compose up -d            # pulls ghcr.io/rojosinalma/cad-render:latest
curl http://localhost:9292/health
bin/cad-render examples/bracket.py -o bracket.stl
```

Pin a release with `CAD_IMAGE_TAG=<version>` in `.env`. Put `bin/cad-render` on your `PATH` and set
`CAD_RENDER_URL` if the service runs elsewhere. To build the image from the checkout instead, see
[docs/development.md](docs/development.md).

## License

[MIT](LICENSE)
