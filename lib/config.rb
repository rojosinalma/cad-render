module Cad
  # Tunables come from the environment so they can change without a rebuild. The service is
  # stateless, so there is no settings DB; defaults live here and nowhere else.
  module Config
    DEFAULTS = {
      "CAD_TIMEOUT_S" => 300,
      "CAD_MAX_JOBS" => 2,
      "CAD_MAX_QUEUE" => 8,
      "CAD_MAX_UPLOAD_MB" => 100,
      "CAD_MAX_FILES" => 2000,
      "ZOO_POLL_S" => 5,
      "ZOO_TIMEOUT_S" => 600,
      "CAD_PYTHON" => "python3",
      "ZOO_API_URL" => "https://api.zoo.dev"
    }.freeze

    def self.fetch(key) = ENV.fetch(key, DEFAULTS.fetch(key))
    def self.int(key) = Integer(fetch(key))

    def self.timeout_s = int("CAD_TIMEOUT_S")
    def self.max_jobs = int("CAD_MAX_JOBS")
    def self.max_queue = int("CAD_MAX_QUEUE")
    def self.max_upload_bytes = int("CAD_MAX_UPLOAD_MB") * 1024 * 1024
    def self.max_files = int("CAD_MAX_FILES")
    def self.zoo_poll_s = int("ZOO_POLL_S")
    def self.zoo_timeout_s = int("ZOO_TIMEOUT_S")
    def self.python = fetch("CAD_PYTHON")
    def self.zoo_api_url = fetch("ZOO_API_URL")
    def self.zoo_token = ENV.fetch("ZOO_API_TOKEN", "")
  end
end
