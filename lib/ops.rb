module Cad
  # Registry of operations: one entry = one worker script + the formats it accepts and emits.
  # Adding an op is a new worker/<op>.py and one line here.
  module Ops
    Unknown = Class.new(StandardError)

    MIME = {
      "stl" => "model/stl", "step" => "application/step", "3mf" => "model/3mf", "png" => "image/png",
      "obj" => "model/obj", "ply" => "application/x-ply", "off" => "model/off", "kcl" => "text/plain",
      "glb" => "model/gltf-binary"
    }.freeze

    MESH_IN = %w[stl 3mf obj ply off].freeze
    BREP_IN = %w[step stp].freeze

    REGISTRY = {
      "render" => { script: "render.py", outputs: %w[stl step 3mf png], default: "stl" },
      "convert" => { script: "convert.py", inputs: MESH_IN + BREP_IN, outputs: %w[stl step 3mf obj ply png], default: "stl" },
      "repair" => { script: "repair.py", inputs: MESH_IN + BREP_IN, outputs: %w[stl 3mf obj ply], default: nil },
      "zoo" => { script: "zoo.py", outputs: %w[step stl 3mf obj ply glb kcl], default: "step" }
    }.freeze

    def self.fetch(name)
      REGISTRY.fetch(name) { raise Unknown, "unknown op #{name.inspect}" }
    end

    def self.script(name) = File.join(__dir__, "..", "worker", fetch(name)[:script])

    def self.output_format(name, requested, fallback: nil)
      op = fetch(name)
      fmt = requested.to_s.downcase
      fmt = (fallback || op[:default]).to_s if fmt.empty?
      return fmt if op[:outputs].include?(fmt)

      raise Worker::Invalid, "unsupported output format #{fmt.inspect} for #{name} (#{op[:outputs].join(', ')})"
    end

    def self.check_input(name, ext)
      op = fetch(name)
      return ext if op[:inputs].nil? || op[:inputs].include?(ext)

      raise Worker::Invalid, "unsupported input .#{ext} for #{name} (#{op[:inputs].join(', ')})"
    end

    def self.mime(ext) = MIME.fetch(ext, "application/octet-stream")
  end
end
