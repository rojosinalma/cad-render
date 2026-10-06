require "open3"
require "json"

module Cad
  # Runs one Python worker script as a subprocess in a work dir, with a hard timeout, and reports
  # the outcome. Workers write their output file to --out and a JSON summary to --meta; everything
  # they print is the log. Exit codes: 0 ok, 3 empty geometry, anything else = failure.
  module Worker
    Invalid = Class.new(StandardError)

    EMPTY_EXIT = 3

    Result = Struct.new(:ok, :empty, :output, :log, :meta, :seconds, :timed_out, :exit_code, :format, :mime,
                        keyword_init: true) do
      def warnings = Array(meta["warnings"])
      def volume = meta["volume_mm3"]
      def bbox = meta["bbox"]
    end

    def self.run(op, workdir:, format:, args: [], timeout_s: Config.timeout_s)
      out = File.join(workdir, ".out.#{format}")
      meta_path = File.join(workdir, ".meta.json")
      cmd = [Config.python, Ops.script(op), "--out", out, "--meta", meta_path, "--format", format, *args]
      started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      log, status, timed_out = exec(cmd, workdir, timeout_s)
      seconds = (Process.clock_gettime(Process::CLOCK_MONOTONIC) - started).round(2)
      meta = read_meta(meta_path)
      output = File.exist?(out) ? File.binread(out) : "".b
      exit_code = status&.exitstatus
      empty = exit_code == EMPTY_EXIT
      ok = !timed_out && (empty || (status&.success? && !output.empty?))
      LOG.info("[worker] #{op} #{format} exit=#{exit_code.inspect} ok=#{ok} empty=#{empty} #{output.bytesize}B #{seconds}s")
      Result.new(ok: ok, empty: empty, output: output, log: log, meta: meta, seconds: seconds,
                 timed_out: timed_out, exit_code: exit_code, format: format, mime: Ops.mime(format))
    end

    def self.read_meta(path)
      File.exist?(path) ? JSON.parse(File.read(path)) : {}
    rescue JSON::ParserError
      {}
    end

    def self.exec(cmd, dir, timeout_s)
      env = { "HOME" => dir, "TMPDIR" => dir, "MPLCONFIGDIR" => dir, "PYTHONDONTWRITEBYTECODE" => "1",
              "ZOO_API_TOKEN" => Config.zoo_token, "ZOO_API_URL" => Config.zoo_api_url,
              "ZOO_POLL_S" => Config.zoo_poll_s.to_s, "ZOO_TIMEOUT_S" => Config.zoo_timeout_s.to_s }
      Open3.popen2e(env, *cmd, chdir: dir, pgroup: true) do |stdin, out, thr|
        stdin.close
        reader = Thread.new { out.read }
        if thr.join(timeout_s)
          [reader.value.to_s, thr.value, false]
        else
          kill(thr.pid)
          [reader.value.to_s + "\nKilled after #{timeout_s}s timeout\n", nil, true]
        end
      end
    end

    def self.kill(pid)
      Process.kill("TERM", -pid)
      sleep 2
      Process.kill("KILL", -pid)
    rescue Errno::ESRCH
      nil
    end

    # Worker environment probe, run once at boot and cached: python + library versions.
    def self.versions
      @versions ||= begin
        log, status = Open3.capture2e(Config.python, File.join(__dir__, "..", "worker", "health.py"))
        status.success? ? JSON.parse(log.lines.last.to_s) : { "ok" => false, "error" => log.strip }
      rescue JSON::ParserError, Errno::ENOENT => e
        { "ok" => false, "error" => e.message }
      end
    end
  end
end
