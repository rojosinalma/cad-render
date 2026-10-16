# CLI

`bin/cad-render` is a bash script that talks to a running service. It needs `bash`, `curl`, `tar` and
`ruby` on the client; put it on your `PATH` and set `CAD_RENDER_URL` when the service is not on
`http://localhost:9292`.

```
cad-render [render] <part.py> -o <out.{stl,step,3mf,png}> [-D name=value]... [--root DIR]
cad-render convert  <in.{step,stl,3mf,obj,ply}> -o <out.{stl,step,3mf,obj,ply,png}>
cad-render repair   <in.{stl,3mf,obj,ply,step}> [-o <out>]          # default: <in>.repaired.<ext>
cad-render zoo      "<prompt>" -o <out.{step,stl,3mf,obj,ply,glb,kcl}>   # also writes <out>.kcl
```

| Option | Meaning |
|---|---|
| `-D name=value` | Define a module global before the script runs (repeatable; `-Dname=value` works too). |
| `--root DIR` | Directory sent as the project tarball (default: the script's directory). |
| `--log` | Print the worker log to stderr. |
| `--to-bb` | Upload the result to the Bambuddy library (`BAMBUDDY_URL` + `BAMBUDDY_API_KEY` required). |
| `--folder <name>` | Bambuddy library folder, matched by name (default: library root). |
| `--pipeline "<name>"` | Bambuddy slicer pipeline, matched by name, run on the uploaded file. |
| `--copies N` | Copies for the pipeline run (default 1). |
| `--dry-run` | With `--to-bb`: check auth, resolve folder and pipeline, upload nothing. |

| Exit | Meaning |
|---|---|
| `0` | OK, file written |
| `1` | Render/convert/repair failure or unreachable service |
| `2` | Usage error |
| `3` | Empty geometry — nothing written (a fit check passed) |
| `4` | Zoo failure |
| `5` | Bambuddy upload or pipeline failure (the local file is kept) |

> **A Bambuddy pipeline run slices *and* may enqueue a print on the target printer.** If an agent
> drives `--to-bb --pipeline`, make sure a human approved that exact job first.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `CAD_RENDER_URL` | `http://localhost:9292` | Service base URL |
| `CAD_RENDER_TIMEOUT` | `900` | curl `--max-time` per request (seconds) |
| `BAMBUDDY_URL` | — | Bambuddy base URL, required for `--to-bb` |
| `BAMBUDDY_API_KEY` | — | Bambuddy API key, required for `--to-bb` |

The Bambuddy upload happens from the CLI on the client; the service never talks to Bambuddy.

## Examples

```sh
cad-render examples/bracket.py -o bracket.step -D hole_d=8 -D fillet_r=3
cad-render examples/bracket.py -o /dev/null -D part=fitcheck; echo $?   # 3
cad-render convert bracket.step -o bracket.3mf
cad-render repair broken.stl                                             # writes broken.repaired.stl
cad-render zoo "a 20 mm cube with a 5 mm through hole" -o cube.stl
cad-render examples/bracket.py -o bracket.3mf --to-bb --folder Parts --dry-run
```
