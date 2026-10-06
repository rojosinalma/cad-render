module Cad
  # Zoo text-to-CAD. Zoo retired the REST `POST /ai/text-to-cad/{format}` endpoint (404 as of
  # 2026-10-06); the only prompt path is the ML copilot websocket (`/ws/ml/copilot`), which returns
  # KCL, and the KCL is turned into a file by the pinned `zoo` CLI (`zoo kcl export`, Engine API).
  # Both steps live in worker/zoo.py; this class owns the Ruby side (validation, timeout, headers),
  # so a Zoo API change touches only this file and that worker.
  module Zoo
    Invalid = Class.new(StandardError)
    MAX_PROMPT = 4000

    def self.generate(prompt:, format:, workdir:)
      raise Invalid, "ZOO_API_TOKEN is not configured" if Config.zoo_token.empty?

      text = prompt.to_s.strip
      raise Invalid, "prompt is required" if text.empty?
      raise Invalid, "prompt exceeds #{MAX_PROMPT} characters" if text.length > MAX_PROMPT

      LOG.info("[zoo] copilot prompt #{text.length} chars -> #{format}")
      # The copilot turn alone takes 30-60 s; the worker enforces ZOO_TIMEOUT_S itself, the outer
      # kill is a backstop.
      Worker.run("zoo", workdir: workdir, format: format, args: ["--prompt", text],
                 timeout_s: Config.zoo_timeout_s + 30)
    end
  end
end
