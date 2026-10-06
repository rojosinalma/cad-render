Encoding.default_external = Encoding::UTF_8

require "dotenv"
Dotenv.load(File.join(__dir__, ".env"))

require "roda"
require "json"
require "logger"
require "tmpdir"
require "base64"
require_relative "lib/config"
require_relative "lib/job_limiter"
require_relative "lib/project_archive"
require_relative "lib/ops"
require_relative "lib/worker"
require_relative "lib/zoo"

module Cad
  LOG = Logger.new($stdout, progname: "cad-render")
  LIMITER = JobLimiter.new
  APP_VERSION = File.read(File.join(__dir__, "VERSION")).strip

  class App < Roda
    plugin :json
    plugin :json_parser, content_type_regexp: %r{\Aapplication/json\b}i
    plugin :error_handler do |e|
      LOG.error("[http] #{e.class}: #{e.message}\n#{e.backtrace&.first(15)&.join("\n")}")
      response.status = 500
      json_err("internal error: #{e.class}: #{e.message}")
    end

    def json_ok(message, **data) = { ok: true, message: message, **data }
    def json_err(message, **data) = { ok: false, message: message, **data }

    route do |r|
      r.root { json_ok("cad-render", version: APP_VERSION, ops: Ops::REGISTRY.keys) }

      r.get("health") { health }

      r.post("render") { job(r) { |dir| render(r.params, dir) } }
      r.post("convert") { job(r) { |dir| convert(r.params, dir) } }
      r.post("repair") { job(r) { |dir| repair(r.params, dir) } }
      r.post("zoo") { job(r) { |dir| zoo(r.params, dir) } }
    end

    private

    def health
      v = Worker.versions
      ok = v["ok"] == true
      response.status = 503 unless ok
      { ok: ok, message: ok ? "ready" : "worker unavailable: #{v['error']}", version: APP_VERSION,
        python: v["python"], build123d: v["build123d"], ocp: v["ocp"], trimesh: v["trimesh"],
        manifold3d: v["manifold3d"], zoo_cli: v["zoo_cli"], zoo_token: !Config.zoo_token.empty?,
        queue: LIMITER.stats }
    end

    # Every op runs through the bounded limiter in a throwaway work dir that is removed afterwards.
    def job(r)
      LIMITER.run do
        Dir.mktmpdir("cad-") do |dir|
          result = yield(dir)
          respond(result, log_mode: truthy(r.params["log"]))
        end
      end
    rescue ProjectArchive::Invalid, Worker::Invalid, Zoo::Invalid, Ops::Unknown => e
      response.status = 422
      json_err(e.message)
    rescue JobLimiter::Busy => e
      response.status = 503
      json_err(e.message)
    end

    def render(params, dir)
      main = stage_script(params, dir)
      format = Ops.output_format("render", params["format"])
      args = ["--main", main]
      defines(params).each { |d| args.push("-D", d) }
      Worker.run("render", workdir: dir, format: format, args: args)
    end

    def convert(params, dir)
      input, _ext = stage_file(params, dir, "convert")
      format = Ops.output_format("convert", params["format"])
      Worker.run("convert", workdir: dir, format: format, args: ["--input", input])
    end

    def repair(params, dir)
      input, ext = stage_file(params, dir, "repair")
      format = Ops.output_format("repair", params["format"], fallback: Ops::MESH_IN.include?(ext) ? ext : "stl")
      Worker.run("repair", workdir: dir, format: format, args: ["--input", input])
    end

    def zoo(params, dir)
      format = Ops.output_format("zoo", params["format"])
      Zoo.generate(prompt: params["prompt"], format: format, workdir: dir)
    end

    # /render input: a project archive (+ main), a single file, or inline source; mirrors openscad.
    def stage_script(params, dir)
      if (upload = params["project"]).is_a?(Hash)
        ProjectArchive.extract(upload[:tempfile], dir)
        main = params["main"].to_s
        main = only_script(dir) if main.empty?
      elsif (upload = params["file"]).is_a?(Hash)
        main = File.basename(upload[:filename].to_s.empty? ? "main.py" : upload[:filename])
        File.binwrite(File.join(dir, main), upload[:tempfile].read(Config.max_upload_bytes))
      elsif params["source"].is_a?(String)
        main = "main.py"
        File.write(File.join(dir, main), params["source"])
      else
        raise Worker::Invalid, "send a project archive (project=@x.tar.gz), a file (file=@part.py) or source"
      end
      path = ProjectArchive.safe_path(dir, main)
      raise Worker::Invalid, "main file #{main.inspect} not found" unless path && File.file?(path)
      raise Worker::Invalid, "main must be a .py script" unless main.end_with?(".py")

      main
    end

    def stage_file(params, dir, op)
      upload = params["file"]
      raise Worker::Invalid, "send the model as file=@model.<ext>" unless upload.is_a?(Hash)

      name = File.basename(upload[:filename].to_s)
      ext = Ops.check_input(op, File.extname(name).delete_prefix(".").downcase)
      raise Worker::Invalid, "cannot tell the input format: #{name.inspect} has no extension" if ext.empty?

      data = upload[:tempfile].read(Config.max_upload_bytes + 1).to_s
      raise Worker::Invalid, "file exceeds #{Config.max_upload_bytes / 1024 / 1024} MB" if data.bytesize > Config.max_upload_bytes
      raise Worker::Invalid, "file is empty" if data.empty?

      path = File.join(dir, "input.#{ext}")
      File.binwrite(path, data)
      ["input.#{ext}", ext]
    end

    def only_script(dir)
      found = Dir.children(dir).select { |f| f.end_with?(".py") }
      raise Worker::Invalid, "archive has #{found.size} top-level .py files; pass main=<path>" unless found.size == 1

      found.first
    end

    DEFINE_RE = /\A[A-Za-z_][A-Za-z0-9_]*=.+\z/m

    def defines(params)
      raw = Array(params["D"]).map(&:to_s)
      if params["defines"].to_s != ""
        raw += JSON.parse(params["defines"]).map { |k, v| "#{k}=#{v.is_a?(String) ? v.to_json : v}" }
      end
      raw.each { |d| raise Worker::Invalid, "bad define #{d.inspect}: expected name=value" unless d.match?(DEFINE_RE) }
      raw
    rescue JSON::ParserError => e
      raise Worker::Invalid, "defines is not a JSON object: #{e.message}"
    end

    def truthy(v) = %w[1 true yes on].include?(v.to_s.downcase)

    def respond(result, log_mode:)
      summary = { empty: result.empty, warnings: result.warnings, seconds: result.seconds,
                  exit_code: result.exit_code, timed_out: result.timed_out,
                  volume_mm3: result.volume, bbox: result.bbox, format: result.format }
      unless result.ok
        response.status = result.timed_out ? 504 : 422
        response["X-Cad-Timeout"] = "1" if result.timed_out
        return json_err(failure_message(result), **summary, log: result.log)
      end
      if log_mode
        extra = result.meta.slice("zoo_id", "zoo_conversation_id", "kcl")
        return json_ok(result.empty ? "rendered: result is empty" : "rendered",
                       **summary, **extra.transform_keys(&:to_sym), log: result.log,
                       bytes: result.output.bytesize, output_base64: Base64.strict_encode64(result.output))
      end
      response["Content-Type"] = result.mime
      response["X-Cad-Version"] = APP_VERSION
      response["X-Cad-Empty"] = result.empty ? "1" : "0"
      response["X-Cad-Warnings"] = result.warnings.size.to_s
      response["X-Cad-Seconds"] = result.seconds.to_s
      response["X-Cad-Volume-mm3"] = result.volume.to_s if result.volume
      response["X-Cad-Bbox"] = Array(result.bbox).join(",") if result.bbox
      response["X-Cad-Zoo-Id"] = result.meta["zoo_id"].to_s if result.meta["zoo_id"]
      result.output
    end

    def failure_message(result)
      return "worker timed out after #{Config.timeout_s}s" if result.timed_out

      err = result.meta["error"].to_s
      err = (result.log.lines.reverse.find { |l| l.match?(/Error|error:/) } || result.log.lines.last).to_s.strip if err.empty?
      "#{result.format} job failed (exit #{result.exit_code}): #{err}"
    end
  end
end
